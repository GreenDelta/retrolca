import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from os import PathLike
from typing import Protocol, override

from retrolca.res import Res


@dataclass
class Reaction:
    score: float
    feasibility: float
    smiles: list[str]


class RetroTool(Protocol):
    """Protocol for retrosynthesis backends.

    Implementations take a product SMILES string and return candidate
    retrosynthesis reactions as Reaction objects.

    Attributes:
        id: Short identifier of the backend or backend configuration.

    Methods:
        expand(smiles): Return candidate one-step retrosynthesis expansions for
        the given product SMILES.
    """

    id: str

    def expand(self, smiles: str) -> Res[list[Reaction]]: ...


class CachingRetroTool(RetroTool):
    def __init__(self, path: str | PathLike, tool: RetroTool):
        self.tool = tool
        self.id = f"{tool.id}/cached"
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tbl_retro_reactions (
                cache_key TEXT PRIMARY KEY,
                reactions_json TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    @override
    def expand(self, smiles: str) -> Res[list[Reaction]]:
        key = self.__key_of(smiles)
        reactions = self.__lookup(key)
        if reactions is not None:
            return reactions, None

        reactions, err = self.tool.expand(smiles)
        if err is not None:
            return None, err
        assert reactions is not None

        self.__store(key, reactions)
        return reactions, None

    def close(self):
        self.conn.close()

    def __key_of(self, smiles: str) -> str:
        raw = f"{self.tool.id}||{smiles}".encode("utf-8")
        return hashlib.blake2b(raw, digest_size=32).hexdigest()

    def __lookup(self, key: str) -> list[Reaction] | None:
        row = self.conn.execute(
            "SELECT reactions_json FROM tbl_retro_reactions WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None

        try:
            data = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return None

        if not isinstance(data, list):
            return None

        reactions: list[Reaction] = []
        try:
            for item in data:
                if not isinstance(item, dict):
                    return None
                reactions.append(Reaction(**item))
        except TypeError:
            return None
        return reactions

    def __store(self, key: str, reactions: list[Reaction]):
        payload = json.dumps(
            [asdict(reaction) for reaction in reactions],
            separators=(",", ":"),
        )
        self.conn.execute(
            """
            INSERT INTO tbl_retro_reactions (cache_key, reactions_json)
            VALUES (?, ?)
            ON CONFLICT(cache_key) DO UPDATE
            SET reactions_json = excluded.reactions_json
            """,
            (key, payload),
        )
        self.conn.commit()
