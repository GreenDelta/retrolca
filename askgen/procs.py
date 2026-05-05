import olca_schema as o

from . import proto, oipc, smiles
from .res import Res, nil, chain_err


class Builder:
    def __init__(self, ctx: oipc.Context, retro: proto.RetroClient):
        self.ctx = ctx
        self.retro = retro

    def build(
        self,
        smiles_code: str,
        name: str | None = None,
        category: str | None = None,
    ) -> Res[o.Process]:
        reactions = self.retro.expand(smiles_code)
        if len(reactions) == 0:
            return nil, f"No results for retrosynthesis of: {smiles_code}"
        reaction = reactions[0]

        # create the reference flow
        ref_flow, err = oipc.create_product(
            self.ctx, smiles_code, name, category
        )
        if err:
            return chain_err("Failed to create reference flow of process", err)

        # create the process
        process = o.new_process(ref_flow.name)  # type: ignore
        process.category = category
        qref = o.new_output(process, ref_flow, 1, self.ctx.mole)
        qref.flow_property = self.ctx.chem_amount.to_ref()
        qref.is_quantitative_reference = True

        # add input flows
        for si in reaction.smiles:
            smiles_i = smiles.canonicalize(si)
            in_flow, err = oipc.create_product(
                self.ctx, smiles_i, category=category
            )
            if err:
                return chain_err("Failed to create input flow", err)

            inp = o.new_input(process, in_flow, 1, self.ctx.mole)
            inp.flow_property = self.ctx.chem_amount.to_ref()

        self.ctx.client.put(process)
        return process, nil
