import olca_schema as o

from . import proto, oipc
from returns.result import  Result, Success, Failure

class Builder:
    def __init__(self, ctx: oipc.Context, retro: proto.RetroClient):
        self.ctx = ctx
        self.retro = retro

    def build(
        self, smiles: str, name: str | None = None, category: str | None = None
    ) -> Result[o.Process, str]:

        reactions = self.retro.expand(smiles)
        if len(reactions) == 0:
            return Failure(f"No results for retrosynthesis of: {smiles}")
        reaction = reactions[0]

        # create the reference flow
        ref_flow = oipc.create_product(self.ctx, smiles, name, category)
        if not ref_flow:
            return Failure(f"Failed to create product from: {smiles}")

        # create the process
        process = o.new_process(ref_flow.name) # type: ignore
        process.category = category
        qref = o.new_output(process, ref_flow, 1, self.ctx.mole)
        qref.is_quantitative_reference = True

        # add input flows
        for smiles_i in reaction.smiles:
            in_flow = oipc.create_product(self.ctx, smiles_i)
            if not in_flow:
                return Failure(f"Failed to create product from: {smiles_i}")
            o.new_input(process, in_flow, 1, self.ctx.mole)

        self.ctx.client.put(process)
        return Success(process)

