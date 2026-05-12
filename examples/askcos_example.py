import logging as log
from pathlib import Path

from retrolca import AskcosClient, AskcosConfig


def main():
    log.basicConfig(
        level=log.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    config = AskcosConfig.from_file(
        Path(__file__).parent.parent / "auth/remote-askcos.json"
    )
    client = AskcosClient(config, model="pistachio")

    reactions = client.expand("CCOP(=O)(OCC)OCC")
    for r in reactions:
        print(r)

    client.logout()


if __name__ == "__main__":
    main()
