import base64
import io
import logging
from typing import Any

import olca_ipc as ipc
import olca_schema as o
from rdkit import Chem
from rdkit.Chem import Draw

from . import oipc, smiles, tool
from .naming import CIR, NamingService
from .res import Res, nil, unwrap

log = logging.getLogger(__name__)


def _find_provider(
    process_uid: str, providers: list[o.TechFlow]
) -> o.TechFlow | None:
    for p in providers:
        if p.provider and p.provider.id == process_uid:
            return p
    log.warning("Could not find process: %s", process_uid)
    return None


class ProcessBuilder:
    def __init__(
        self,
        ctx: oipc.IpcContext,
        tool: tool.RetroTool,
        max_variants=3,
        max_levels=5,
        gen_process: str | None = None,
        bal_process: str | None = None,
        naming: NamingService = CIR(),
    ):
        """Constructs a new process builder.

        Args:
            ctx:
                The IPC context for data exchange with openLCA.
            tool:
                The retrosynthesis tool.
            max_variants:
                The maximum number of process variants that can be created at
                each level. Default is 3.
            max_levels:
                The maximum number of levels, or supply-chain depth, to
                generate. At each level, the builder tries to link providers.
                If no provider can be linked earlier, generation continues up
                to this depth. Default is 5.
            gen_process:
                An optional ID of a generic chemical production process that
                should be linked to the generated processes. This process needs
                to have a single product output measured in mass. It is linked
                as an input to the generated processes. Each generated process
                has an output of 1 kg of the respective product. Thus, the
                generic production process is also linked with 1 kg input.
        """
        self.ctx = ctx
        log.info("Build provider and flow index")
        self.providers = oipc.ProviderIndex.of(ctx)
        self.flows = oipc.FlowIndex.of(ctx)
        self.tool = tool
        self.max_variants = max_variants
        self.max_levels = max_levels

        self.gen_provider: o.TechFlow | None = None
        self.bal_provider: o.TechFlow | None = None
        if gen_process or bal_process:
            providers = ctx.client.get_providers()
            if gen_process:
                self.gen_provider = _find_provider(gen_process, providers)
            if bal_process:
                self.bal_provider = _find_provider(bal_process, providers)
        self.naming = naming

    def build(
        self,
        smiles_code: str,
        name: str | None = None,
        category: str | None = None,
        level=0,
    ) -> list[o.Process]:
        """Build process variants for a product SMILES code.

        Args:
            smiles_code:
                The product SMILES code for which retrosynthesis processes
                should be generated.
            name:
                An optional display name for the product flow. If omitted, the
                naming service is used and falls back to the SMILES code.
            category:
                An optional root category path under which generated processes,
                flows, and sources are stored in openLCA. For generated
                processes, subcategories for the respective levels are created
                under that path.
            level:
                The current recursion level. This is managed internally during
                recursive expansion and usually stays at the default value.
        """
        log.info(
            "Create processes for SMILES=%s at level=%d", smiles_code, level
        )
        ref_flow = self.__resolve_product(smiles_code, name, category)
        if not ref_flow:
            return []
        mm_prod = self.ctx.molar_mass_of(ref_flow)
        if not mm_prod:
            return []
        reactions = self.__get_reactions(smiles_code)
        if len(reactions) == 0:
            return []

        variant = 0
        processes = []
        for reaction in reactions:
            variant += 1
            process = self.__init_process(
                ref_flow, reaction, variant, smiles_code, category, level
            )

            for si in reaction.smiles:
                smiles_i = smiles.canonicalize(si)
                provider = self.__resolve_provider(
                    smiles_i, category, level + 1
                )
                if not provider:
                    continue
                flow = unwrap(provider.flow)
                mm_react = self.ctx.molar_mass_of(flow)
                if not mm_react:
                    continue

                # with n: chemical amount, m: mass, and mm: molar mass
                # as we have a reaction of 1 mol reactant (input) and
                # 1 mol product (output) with mm = m / n
                # n_inp = n_out = 1 mol
                # n_out = m_out / mm_out
                # m_inp = n_inp * mm_inp
                # m_inp = n_out * mm_inp
                # m_inp = (m_out / mm_out) * mm_inp
                # m_inp = m_out * mm_inp / mm_out  | m_out = 1 (kg)
                # m_inp = mm_inp / mm_out
                amount = mm_react / mm_prod
                inp = o.new_input(process, flow, amount, self.ctx.kg)
                inp.flow_property = self.ctx.mass.to_ref()
                inp.default_provider = provider.provider
            self.ctx.client.put(process)
            log.info("Created process %s", process.name)
            processes.append(process)
            if variant == 1:
                self.providers.put(smiles_code, process)
        return processes

    def __get_reactions(self, smiles_code: str) -> list[tool.Reaction]:
        reactions, err = self.tool.expand(smiles_code)
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
        reaction: tool.Reaction,
        variant: int,
        product_smiles: str,
        category: str | None,
        level: int,
    ) -> o.Process:
        score = reaction.score * reaction.feasibility
        name = (
            f"production of {ref_flow.name} | variant {variant} "
            f"| c = {score:.4f}"
        )
        process = o.new_process(name)
        process.category = category
        if level > 0 and process.category:
            process.category += f"/level {level}"

        qref = o.new_output(process, ref_flow, 1, self.ctx.kg)
        qref.flow_property = self.ctx.mass.to_ref()
        qref.is_quantitative_reference = True
        process.other_properties = {
            "Retrosynthesis-Score": reaction.score,
            "Retrosynthesis-Feasibility": reaction.feasibility,
        }
        self.__add_reaction_source(process, product_smiles, reaction, category)
        self.__add_gen_input(process)
        return process

    def __resolve_provider(
        self, smiles_code: str, category: str | None, level: int
    ) -> o.TechFlow | None:
        if p := self.providers.get(smiles_code):
            return p
        if level > self.max_levels:
            flow = self.__resolve_product(smiles_code, category=category)
            return o.TechFlow(flow=flow.to_ref()) if flow else None
        processes = self.build(smiles_code, category=category, level=level)
        if len(processes) == 0:
            return None
        return self.providers.put(smiles_code, processes[0])

    def __resolve_product(
        self,
        smiles_code: str,
        name: str | None = None,
        category: str | None = None,
    ) -> o.Flow | None:
        flow = self.flows.data.get(smiles_code)
        if flow:
            return flow
        log.info("Create flow for SMILES: %s", smiles_code)
        flow, err = self.create_product(smiles_code, name, category)
        if err:
            log.error("Failed to create flow for SMILES: %s", smiles_code)
            return None
        assert flow
        self.flows.data[smiles_code] = flow
        return flow

    def __add_reaction_source(
        self,
        process: o.Process,
        smiles_code: str,
        reaction: tool.Reaction,
        category: str | None,
    ):
        image_data = self.__reaction_image(smiles_code, reaction)
        if not image_data:
            return
        source = o.Source(name=f"Reaction scheme for {process.name}")
        source.category = category
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
        self, product_smiles: str, reaction: tool.Reaction
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
            labels.append(self.naming.get_name(code))

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

    def __add_gen_input(self, process: o.Process):
        if not self.gen_provider or not self.gen_provider.flow:
            return
        inp = o.new_input(
            process,
            unwrap(self.gen_provider.flow),
            1,
            self.ctx.kg,
        )
        inp.flow_property = self.ctx.mass.to_ref()
        inp.default_provider = self.gen_provider.provider

    def __add_bal_exchange(self, process: o.Process, amount: float):
        if not self.bal_provider or not self.bal_provider.flow:
            return
        flow = unwrap(self.bal_provider.flow)
        exchange: o.Exchange
        if flow.flow_type == o.FlowType.PRODUCT_FLOW:
            exchange = o.new_input(process, flow, amount, self.ctx.kg)
            exchange.is_avoided_product = True
        else:
            exchange = o.new_output(process, flow, amount, self.ctx.kg)
        exchange.flow_property = self.ctx.mass.to_ref()
        exchange.default_provider = self.bal_provider.provider

    def create_product(
        self,
        smiles_code: str,
        name: str | None = None,
        category: str | None = None,
    ) -> Res[o.Flow]:
        info = self.naming.get_info(smiles_code)
        product: str
        if name:
            product = name
        elif info:
            product = info.name
        else:
            product = smiles_code

        flow = o.new_product(product, self.ctx.mass)
        if not flow or not flow.flow_properties:
            return nil, "Could not create product flow"
        flow.category = category
        flow.description = (
            "This product flow was automatically generated from it's SMILES code. "
            "See also see the additional properties of the flow for more "
            "information."
        )

        # add the chemical amount as flow property
        mw = smiles.mol_weight(smiles_code)
        if not mw:
            return nil, f"Could not calculate the molar mass of: {smiles_code}"
        flow.flow_properties.append(
            o.FlowPropertyFactor(
                conversion_factor=1000 / mw,
                flow_property=self.ctx.chem_amount.to_ref(),
            )
        )

        # additional properties
        props: dict[str, Any] = {}
        flow.other_properties = props
        props["SMILES"] = smiles_code
        props["MolarMass"] = mw
        if info:
            flow.formula = info.formula
            if info.inchi:
                props["InChI-String"] = info.inchi
            if info.inchi_key:
                props["InChI-Key"] = info.inchi_key

        self.ctx.client.put(flow)
        return flow, nil
