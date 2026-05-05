import csv

import olca_ipc as ipc
import olca_schema as lca

import askgen.oipc as oicp

from rdkit import Chem

from askgen import smiles


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
    client = ipc.Client()
    ctx, err = oicp.Context.load(client)
    if err:
        raise SystemExit(1)
    flows = oicp.FlowIndex.load(ctx).data.values()

    with open("out/scitolub_chems.csv", "w", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Flow",
                "UUID",
                "Mass - declared [kg]",
                "Chemical amount - declared [mol]",
                "Molar mass - declared [g/mol]",
                "SMILES",
                "Molar mass - from SMILES [g/mol]",
            ]
        )

        for flow in flows:
            mm_decl = ctx.molar_mass_of(flow)
            code = smiles.of_flow(flow)
            mm_calc = smiles.mol_weight(code)
            mass_prop = next(
                filter(
                    lambda prop: prop.flow_property.id == oicp._MASS_ID,
                    flow.flow_properties,
                )
            )
            chem_prop = next(
                filter(
                    lambda prop: prop.flow_property.id
                    == oicp._CHEMICAL_AMOUNT_ID,
                    flow.flow_properties,
                )
            )
            w.writerow(
                [
                    flow.name,
                    flow.id,
                    mass_prop.conversion_factor,
                    chem_prop.conversion_factor,
                    mm_decl,
                    code,
                    mm_calc,
                ]
            )
