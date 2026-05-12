import logging
from pathlib import Path

import retrolca as r


def main():
    """
    (
        "sucralose",
        "C([C@@H]1[C@@H]([C@@H]([C@H]([C@H](O1)O[C@]2([C@H]([C@@H]([C@H](O2)CCl)O)O)CCl)O)O)Cl)O",
    ),
    ("sorbitol", "C([C@H]([C@H]([C@@H]([C@H](CO)O)O)O)O)O"),
    """

    inputs = [
        ("1-butylpyrrolidin-2-one", "CCCCN1CCCC1=O"),
        ("1-(2-Hydroxyethyl)-2-pyrrolidinone", "C1CC(=O)N(C1)CCO"),
        ("triethyl phosphate", "CCOP(=O)(OCC)OCC"),
        (
            "Polyethylene Glycol 3000",
            "C1=CC=C2C(=C1)C(C3=CC=CC=C32)COC(=O)NCCOCCOCCC(=O)O.N",
        ),
        ("4-tert-Octylphenol", "CC(C)(C)CC(C)(C)C1=CC=C(C=C1)O"),
    ]

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    # auth_file = "auth/local.json"
    auth_file = Path("auth/remote.json")
    auth = r.AskcosConfig.from_file(auth_file)

    with r.AskcosClient(auth) as client:
        for name, input in inputs:
            file_name = f"{name}_{input}"
            csv_path = Path(f"out/{file_name}.csv")
            if csv_path.exists():
                continue

            reactions, err = client.expand(input)
            if err:
                logging.error("ASKCOS expansion failed for %s: %s", input, err)
                continue
            assert reactions is not None

            csv = name + " :: " + input + ":\n"
            for reaction in reactions:
                csv += str(reaction.score)
                for smiles in reaction.smiles:
                    csv += "," + smiles
                csv += "\n"

            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(csv)


if __name__ == "__main__":
    main()
