import logging

import olca_ipc as ipc

import askgen.zynth as z
import askgen.oipc as oipc
import askgen.procs as procs


def test_zynth():
    config = z.ZynthConfig.from_file("auth/local-zynth.json")
    client = z.ZynthClient(config)
    reactions = client.expand("CCCCN1CCCC1=O")

    for r in reactions:
        print(r)
        print(r.score * r.feasibility)
        print("------")


def main():
    logging.basicConfig(level=logging.INFO)
    config = z.ZynthConfig.from_file("auth/local-zynth.json")
    zynth_client = z.ZynthClient(config)
    ctx, _ = oipc.Context.of(ipc.Client())
    builder = procs.Builder(
        ctx,
        zynth_client,
        category="Retrosynthesis/Inbox",
        max_levels=5,
        max_variants=2
    )
    builder.build("CCCCN1CCCC1=O", "1-butylpyrrolidin-2-one")


if __name__ == "__main__":
    main()
