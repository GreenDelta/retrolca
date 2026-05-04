import olca_schema as o

from . import proto, oipc, smiles
from returns.result import Result, Success, Failure


class Builder:
    def __init__(self, ctx: oipc.Context, retro: proto.RetroClient):
        self.ctx = ctx
        self.retro = retro

    def build(
        self,
        smiles_code: str,
        name: str | None = None,
        category: str | None = None,
    ) -> Result[o.Process, str]:

        reactions = self.retro.expand(smiles_code)
        if len(reactions) == 0:
            return Failure(f"No results for retrosynthesis of: {smiles_code}")
        reaction = reactions[0]

        # create the reference flow
        match r := oipc.create_product(self.ctx, smiles_code, name, category):
            case Failure(error):
                return Failure(
                    f"Failed to create reference flow of process:\n  -> {error}"
                )
            case _:
                ref_flow = r.unwrap()

        # create the process
        process = o.new_process(ref_flow.name)  # type: ignore
        process.category = category
        qref = o.new_output(process, ref_flow, 1, self.ctx.mole)
        qref.flow_property = self.ctx.chem_amount.to_ref()
        qref.is_quantitative_reference = True

        # add input flows
        for si in reaction.smiles:
            smiles_i = smiles.canonicalize(si)
            r = oipc.create_product(self.ctx, smiles_i, category=category)
            match r:
                case Failure(error):
                    return Failure(
                        f"Failed to create input flow:\n  -> {error}"
                    )
                case _:
                    in_flow = r.unwrap()
            inp = o.new_input(process, in_flow, 1, self.ctx.mole)
            inp.flow_property = self.ctx.chem_amount.to_ref()

        self.ctx.client.put(process)
        return Success(process)

