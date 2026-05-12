import logging as log
from pathlib import Path

from retrolca import AskcosClient, AskcosConfig, AskcosModel


def main():
    log.basicConfig(
        level=log.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    config = AskcosConfig.from_file(
        Path(__file__).parent.parent / "auth/remote-askcos.json"
    )

    with AskcosClient(config, model=AskcosModel.PISTACHIO) as client:
        reactions, _ = client.expand("CCOP(=O)(OCC)OCC")
        assert reactions
        for r in reactions:
            print(r)


if __name__ == "__main__":
    main()
