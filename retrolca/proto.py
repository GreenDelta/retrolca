from dataclasses import dataclass
from typing import Protocol

from retrolca.res import Res


@dataclass
class Reaction:
    score: float
    feasibility: float
    smiles: list[str]


class RetroClient(Protocol):
    def expand(self, smiles: str) -> Res[list[Reaction]]: ...
