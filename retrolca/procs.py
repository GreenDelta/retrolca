import base64
import io
import logging

import olca_ipc as ipc
import olca_schema as o
from rdkit import Chem
from rdkit.Chem import Draw

from . import oipc, proto, smiles
from .res import unwrap

log = logging.getLogger(__name__)


def _find_gen_provider(
    client: ipc.ProtoClient, gen_process: str
) -> o.TechFlow | None:
    for p in client.get_providers():
        if p.provider and p.provider.id == gen_process:
            return p
    return None


class ProcessBuilder:
    def __init__(
        self,
        ctx: oipc.IpcContext,
        retro: proto.RetroClient,
        max_variants=3,
        max_levels=5,
        category: str | None = None,
        gen_process: str | None = None,
    ):
        """Constructs a new process builder.

        Args:
            ctx:
                The IPC context for data exchange with openLCA.
            retro:
                The retrosynthesis tool.
            max_variants:
                The maximum number of variants of a process that can be created
                at each level. (default 3)
            max_levels:
                The maximum number of levels, so depth of the supply chain, that
                can be generated. At each level the builder will try to link
                providers, this is the maximum level, if no providers can be
                linked before. (default 5)
            category:
                An optional root category path under which generated processes
                and flows are stored in openLCA. Additionally, sub-categories
                are created for the respective levels under that path.
            gen_process:
                An optional ID of a generic chemical production process that
                should be linked to the generated processes. This process needs
                to have a single product output given in mass. It is then linked
                as an input in the generated processes. Each generated process
                has an output of 1 mol of the respective product. With the molar
                mass of that product we calculate the corresponding mass of the
                input from the generic production process.
        """
        self.ctx = ctx
        log.info("Build provider and flow index")
        self.providers = oipc.ProviderIndex.of(ctx)
        self.flows = oipc.FlowIndex.of(ctx)
        self.retro = retro
        self.max_variants = max_variants
        self.max_levels = max_levels
        self.category = category

    def build(
        self,
        smiles_code: str,
        name: str | None = None,
        level=0,
    ) -> list[o.Process]:
        log.info(
            "Create processes for SMILES=%s at level=%d", smiles_code, level
        )
        ref_flow = self.__resolve_product(smiles_code, name)
        if not ref_flow:
            return []
        reactions = self.__get_reactions(smiles_code)
        if len(reactions) == 0:
            return []

        variant = 0
        processes = []
        for reaction in reactions:
            variant += 1
            process = self.__init_process(
                ref_flow, reaction, variant, smiles_code, level
            )
            for si in reaction.smiles:
                smiles_i = smiles.canonicalize(si)
                provider = self.__resolve_provider(smiles_i, level + 1)
                if not provider:
                    continue
                inp = o.new_input(
                    process, unwrap(provider.flow), 1, self.ctx.mole
                )
                inp.flow_property = self.ctx.chem_amount.to_ref()
                inp.default_provider = provider.provider
            self.ctx.client.put(process)
            log.info("Created process %s", process.name)
            processes.append(process)
            if variant == 1:
                self.providers.put(smiles_code, process)
        return processes

    def __get_reactions(self, smiles_code: str) -> list[proto.Reaction]:
        reactions, err = self.retro.expand(smiles_code)
        if err:
            log.info(
                "No retrosynthesis results retrieved for %s: %s",
                smiles_code,
                err,
            )
            return []
        if not isinstance(reactions, list) or len(reactions) == 0:
            log.info("No retrosynthesis results retrieved for: %s", smiles_code)
            return []

        reactions.sort(key=lambda r: r.score * r.feasibility, reverse=True)
        if len(reactions) > self.max_variants:
            reactions = reactions[0 : self.max_variants]
        return reactions

    def __init_process(
        self,
        ref_flow: o.Flow,
        reaction: proto.Reaction,
        variant: int,
        product_smiles: str,
        level: int,
    ) -> o.Process:
        score = reaction.score * reaction.feasibility
        name = (
            f"production of {ref_flow.name} | variant {variant} "
            f"| c = {score:.4f}"
        )
        process = o.new_process(name)
        process.category = self.category
        if level > 0 and process.category:
            process.category += f"/level {level}"

        qref = o.new_output(process, ref_flow, 1, self.ctx.mole)
        qref.flow_property = self.ctx.chem_amount.to_ref()
        qref.is_quantitative_reference = True
        process.other_properties = {
            "Retrosynthesis-Score": reaction.score,
            "Retrosynthesis-Feasibility": reaction.feasibility,
        }
        self.__add_reaction_source(process, product_smiles, reaction)
        return process

    def __resolve_provider(
        self, smiles_code: str, level: int
    ) -> o.TechFlow | None:
        if p := self.providers.get(smiles_code):
            return p
        if level > self.max_levels:
            flow = self.__resolve_product(smiles_code)
            return o.TechFlow(flow=flow.to_ref()) if flow else None
        processes = self.build(smiles_code, level=level)
        if len(processes) == 0:
            return None
        return self.providers.put(smiles_code, processes[0])

    def __resolve_product(
        self, smiles_code: str, name: str | None = None
    ) -> o.Flow | None:
        flow = self.flows.data.get(smiles_code)
        if flow:
            return flow
        log.info("Create flow for SMILES: %s", smiles_code)
        flow, err = oipc.create_product(
            self.ctx, smiles_code, name, self.category
        )
        if err:
            log.error("Failed to create flow for SMILES: %s", smiles_code)
            return None
        assert flow
        self.flows.data[smiles_code] = flow
        return flow

    def __add_reaction_source(
        self, process: o.Process, smiles_code: str, reaction: proto.Reaction
    ):
        image_data = self.__reaction_image(smiles_code, reaction)
        if not image_data:
            return
        source = o.Source(name=f"Reaction scheme for {process.name}")
        source.category = self.category
        source.description = (
            "This source was automatically generated for the retrosynthesis "
            f"reaction assigned to the process '{process.name}'. It includes "
            "an image showing the reactant molecules together with the product "
            "molecule."
        )
        source_ref = self.ctx.client.put(source)
        if not source_ref:
            log.error("Failed to create reaction source for %s", process.name)
            return

        uploaded = self.ctx.client.put_source_file(
            source_ref, ipc.FileData("reaction.png", image_data)
        )
        if not uploaded:
            log.error(
                "Failed to upload reaction image for process %s",
                process.name,
            )

        process.process_documentation = o.ProcessDocumentation()
        process.process_documentation.sources = [source_ref]

    def __reaction_image(
        self, product_smiles: str, reaction: proto.Reaction
    ) -> str | None:
        codes = [smiles.canonicalize(code) for code in reaction.smiles]
        codes.append(product_smiles)

        mols = []
        labels = []
        for code in codes:
            mol = Chem.MolFromSmiles(code)
            if not mol:
                log.warning("Could not render molecule for SMILES: %s", code)
                continue
            mols.append(mol)
            labels.append(self.__molecule_label(code))

        if len(mols) == 0:
            return None

        img = Draw.MolsToGridImage(
            mols,
            molsPerRow=len(mols),
            subImgSize=(200, 200),
            legends=labels,
        )
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def __molecule_label(self, smiles_code: str) -> str:
        info = smiles.get_cirpy_info(smiles_code)
        if info and info.name:
            return info.name
        return smiles_code
