import json
import logging as log
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from retrolca import AskcosClient


@dataclass
class Config:
    endpoint: str
    user: str
    password: str

    @classmethod
    def read(cls, path: Path) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)
            return Config(**config)


def main():
    log.basicConfig(
        level=log.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    config = Config.read(
        Path(__file__).parent.parent / "auth/remote-askcos.json"
    )
    client = AskcosClient(config.endpoint, model="pistachio")
    client.login(config.user, config.password)

    reactions = client.expand("CCOP(=O)(OCC)OCC")
    for r in reactions:
        print(r)

    client.logout()


if __name__ == "__main__":
    main()
