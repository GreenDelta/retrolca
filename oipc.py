import olca_ipc as ipc
import olca_schema as lca

import askgen.oipc as oicp
import askgen.procs as procs
import askgen.zynth as zynth

from rdkit import Chem


def main():
    client = ipc.Client()
    for flow in client.get_all(lca.Flow):
        if not flow.other_properties:
            continue
        code = flow.other_properties.get("Absolute-SMILES")
        if not code:
            continue
        mol = Chem.MolFromSmiles(code)
        canonicalized = Chem.MolToSmiles(
            mol, isomericSmiles=True, canonical=True
        )
        print(f"{flow.name} :: {code}  :: {canonicalized}")


if __name__ == "__main__":
    # main()
    code = "CCCCN1CCCC1=O"
    ctx = oicp.Context.load(ipc.Client())
    zynth_config = zynth.ZynthConfig.from_file("auth/local-zynth.json")
    zynth_client = zynth.ZynthClient(zynth_config)
    builder = procs.Builder(ctx, zynth_client)
    process, err = builder.build(code, category="Test")
    if err:
        print(f"ERROR: {err}")
    else:
        print(f"Created process: {process.id}")
