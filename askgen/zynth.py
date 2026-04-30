import json
from dataclasses import dataclass
from os import PathLike

import requests


@dataclass
class Reaction:
    score: float
    feasibility: float
    smiles: list[str]


@dataclass
class ZynthConfig:
    endpoint: str
    token: str

    @staticmethod
    def from_file(path: str | PathLike) -> "ZynthConfig":
        with open(path, "r", encoding="utf-8") as f:
            d: dict = json.load(f)
            return ZynthConfig(**d)


class ZynthClient:

    def __init__(self, config: ZynthConfig):
        self.endpoint = config.endpoint.strip().rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-API-Token"] = config.token

    def expand(self, smiles: str) -> list[Reaction]:
        url = self.endpoint + "/expand"
        resp = self.session.post(url, json={"smiles": smiles})
        resp.raise_for_status()
        return [Reaction(**d) for d in resp.json()]
