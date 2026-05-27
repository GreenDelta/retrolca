import json
import logging
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import override

import aizynthfinder.aizynthfinder as ai
import requests

from .tool import Reaction, RetroTool
from .res import Res, nil

log = logging.getLogger(__name__)


class ZynthTool(RetroTool):
    def __init__(self, configfile: str | Path):
        log.info("Loading AiZynthExpander with config: %s", configfile)
        self.id = "zynth"
        self.expander = ai.AiZynthExpander(configfile=str(configfile))
        self.expander.expansion_policy.select("uspto")
        self.expander.filter_policy.select("uspto")

    @override
    def expand(self, smiles: str) -> Res[list[Reaction]]:
        log.info("Expand SMILES code: %s", smiles)
        reactions: list[Reaction] = []
        expansion = self.expander.do_expansion(smiles)
        for group in expansion:
            reaction: Reaction | None = None
            for candidate in group:
                # for the same reactants there could be multiple reactions with
                # different scores
                r = _reaction_of(candidate)
                if not r:
                    continue
                if reaction and reaction.score > r.score:
                    continue
                reaction = r
            if reaction:
                reactions.append(reaction)
        log.info("Found %d reactions", len(reactions))
        return reactions, None


def _reaction_of(r: ai.FixedRetroReaction) -> Reaction | None:
    if not r or not r.metadata or not r.reactants:
        return None
    meta = r.metadata
    score = meta.get("policy_probability", 0.0)
    feasibility = meta.get("feasibility", 0.0)
    smiles = []
    for reactants in r.reactants:
        for mol in reactants:
            smiles.append(mol.smiles)
    if len(smiles) == 0:
        return None
    return Reaction(score=score, feasibility=feasibility, smiles=smiles)


@dataclass
class ZynthConfig:
    endpoint: str
    token: str

    @staticmethod
    def from_file(path: str | PathLike) -> "ZynthConfig":
        with open(path, "r", encoding="utf-8") as f:
            d: dict = json.load(f)
            return ZynthConfig(**d)


class ZynthClient(RetroTool):
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
