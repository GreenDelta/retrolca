import json
from dataclasses import dataclass
from os import PathLike
from typing import override

from .proto import Reaction, RetroClient
from .res import Res, nil
import requests


@dataclass
class ZynthConfig:
    endpoint: str
    token: str

    @staticmethod
    def from_file(path: str | PathLike) -> "ZynthConfig":
        with open(path, "r", encoding="utf-8") as f:
            d: dict = json.load(f)
            return ZynthConfig(**d)


class ZynthClient(RetroClient):
    def __init__(self, config: ZynthConfig):
        self.endpoint = config.endpoint.strip().rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-API-Token"] = config.token

    def __enter__(self) -> "ZynthClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @override
    def expand(self, smiles: str) -> Res[list[Reaction]]:
        try:
            url = self.endpoint + "/expand"
            resp = self.session.post(url, json={"smiles": smiles})
            resp.raise_for_status()
            return [Reaction(**d) for d in resp.json()], nil
        except Exception as err:
            return nil, str(err)

    def close(self) -> None:
        self.session.close()
