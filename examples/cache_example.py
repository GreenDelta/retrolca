from pathlib import Path

import retrolca as r


def main():
    root = Path(__file__).parent.parent

    login = r.AskcosLogin.from_file(root / "auth/remote-askcos.json")
    tool = r.AskcosClient(login, model=r.AskcosModel.PISTACHIO)
    caching_tool = r.CachingRetroTool(root / "out/cached_reactions.db", tool)

    reactions, err = caching_tool.expand("CCOP(=O)(OCC)OCC")
    if err or not reactions:
        print("Query failed: ", err)
        return

    for rc in reactions:
        print(f"score: {rc.score} feasibility:{rc.feasibility} :: {rc.smiles}")

    caching_tool.close()


if __name__ == "__main__":
    main()
