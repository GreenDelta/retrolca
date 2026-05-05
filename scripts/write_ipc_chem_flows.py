"""Export openLCA chemical product flows to a CSV file.

This script exports chemical products for which mass, chemical amount, and a
SMILES code are defined. It writes both the declared molar mass and the molar
mass calculated from the SMILES code so these values can be compared.
"""

import csv
from pathlib import Path

import olca_ipc as ipc

from askgen import smiles
from askgen import oipc

ROOT = Path(__file__).parent.parent


def main() -> None:
    client = ipc.Client()
    ctx, err = oipc.Context.load(client)
    if err:
        print(f"ERROR: {err}")
        return

    flows = oipc.FlowIndex.load(ctx).data.values()
    out_path = ROOT / "out/scitolub_chems.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as f:
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
                prop
                for prop in flow.flow_properties
                if prop.flow_property and prop.flow_property.id == oipc._MASS_ID
            )
            chem_prop = next(
                prop
                for prop in flow.flow_properties
                if prop.flow_property
                and prop.flow_property.id == oipc._CHEMICAL_AMOUNT_ID
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


if __name__ == "__main__":
    main()
