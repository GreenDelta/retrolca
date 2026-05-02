import olca_ipc as ipc
import olca_schema as lca

import askgen.oipc as oicp

import askgen.smiles as smiles

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
        canonicalized = Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)
        print(f"{flow.name} :: {code}  :: {canonicalized}")


if __name__ == "__main__":
    # main()
    code = "C1=NC=NN1"
    print(smiles.mol_weight(code))
    print(smiles.as_uid(code))

    ctx = oicp.Context.load(ipc.Client())
    print(ctx.mole.name)
