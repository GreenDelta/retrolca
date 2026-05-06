import logging as log
import olca_schema as o

from . import proto, oipc, smiles
from .res import unwrap


class Builder:
    def __init__(
        self,
        ctx: oipc.Context,
        retro: proto.RetroClient,
        max_variants=3,
        max_levels=5,
        category: str | None = None,
    ):
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

        reactions = self.retro.expand(smiles_code)
        if len(reactions) == 0:
            log.info("No retrosynthesis results retrieved for: %s", smiles_code)
            return []

        reactions.sort(key=lambda r: r.score * r.feasibility, reverse=True)
        if len(reactions) > self.max_variants:
            reactions = reactions[0 : self.max_variants]

        variant = 0
        processes = []
        for reaction in reactions:
            variant += 1
            process = self.__init_process(ref_flow, reaction, variant)
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

    def __init_process(
        self, ref_flow: o.Flow, reaction: proto.Reaction, variant: int
    ):
        score = reaction.score * reaction.feasibility
        name = (
            f"production of {ref_flow.name} | variant {variant} "
            f"| c = {score:.4f}"
        )
        process = o.new_process(name)
        process.category = self.category
        qref = o.new_output(process, ref_flow, 1, self.ctx.mole)
        qref.flow_property = self.ctx.chem_amount.to_ref()
        qref.is_quantitative_reference = True
        process.other_properties = {
            "Retrosynthesis-Score": reaction.score,
            "Retrosynthesis-Feasibility": reaction.feasibility,
        }
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
        self.flows.data[smiles_code] = flow
        return flow

    def __add_reaction_source(self, process: o.Process, smiles_code: str, reaction: proto.Reaction):
        source = o.Source(name=process.name)
        self.ctx.client.put()

        process.process_documentation = o.ProcessDocumentation()
        process.process_documentation.sources = [
            source.to_ref()
        ]
