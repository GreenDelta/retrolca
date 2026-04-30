from dataclasses import dataclass
from typing import Protocol


@dataclass
class Reaction:
    score: float
    feasibility: float
    smiles: list[str]


class RetroClient(Protocol):
    def expand(self, smiles: str) -> list[Reaction]: ...
