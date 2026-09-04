from pathlib import Path

import retrolca as retro


def main():
    root = Path(__file__).parent.parent

    login = retro.AskcosLogin.from_file(root / "auth/remote-askcos.json")
    client = retro.AskcosClient(login, model=retro.AskcosModel.REAXYS)

    reactions, err = client.expand("CCOP(=O)(OCC)OCC")
    if err or not reactions:
        print("Query failed: ", err)
        return

    for r in reactions:
        print(f"score: {r.score} feasibility:{r.feasibility} :: {r.smiles}")

    client.close()


if __name__ == "__main__":
    main()
