import json
import logging
from pathlib import Path

import askgen as ask


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
    auth_file = "auth/remote.json"
    auth = ask.Auth.read(auth_file)

    client = ask.Client(auth)
    client.login()

    for name, input in inputs:
        file_name = f"{name}_{input}"
        csv_path = Path(f"out/{file_name}.csv")
        if csv_path.exists():
            continue

        req = ask.RetroRequest.of(input)
        task_id = client.run(req)
        resp = client.poll(task_id)

        csv = name + " :: " + input + ":\n"
        for result in resp.results:
            csv += str(result.score)
            for smiles in result.outcome:
                csv += "," + smiles
            csv += "\n"

        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv)

        with open(f"out/{file_name}.json", "w", encoding="utf-8") as f:
            json.dump(resp.data, f)

    client.logout()


if __name__ == "__main__":
    main()
