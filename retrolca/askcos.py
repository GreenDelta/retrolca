import json
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, override

import requests

from .proto import Reaction, RetroClient
from .res import Res, chain_err, nil

log = logging.getLogger(__name__)


class AskcosModel(StrEnum):
    BKMS_METABOLIC = "bkms_metabolic"
    PISTACHIO = "pistachio"
    PISTACHIO_RINGBREAKER = "pistachio_ringbreaker"
    REAXYS = "reaxys"
    REAXYS_BIOCATALYSIS = "reaxys_biocatalysis"
    USPTO_HIGHER_LEVEL = "uspto_higher_level"


@dataclass
class AskcosConfig:
    endpoint: str
    user: str
    password: str

    @classmethod
    def from_file(cls, path: Path) -> "AskcosConfig":
        with open(path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)
            return AskcosConfig(**config)


def _request_of(
    smiles_code: str, model: AskcosModel = AskcosModel.PISTACHIO
) -> dict[str, Any]:
    return {
        "smiles": smiles_code,
        "retro_backend_options": [
            {
                "retro_backend": "template_relevance",
                "max_num_templates": 1000,
                "max_cum_prob": 0.999,
                "retro_model_name": model.value,
            }
        ],
        "retro_rerank_backend": "relevance_heuristic",
        "atom_map_backend": "rxnmapper",
        "use_fast_filter": True,
        "fast_filter_threshold": 0.1,
        "cluster_precursors": False,
    }


def _reactions_of(response: dict[str, Any]) -> list[Reaction]:
    """Extracts the reactions from an ASKCOS response, if available."""
    if not isinstance(response, dict):
        return []
    output = response.get("output")
    if not isinstance(output, dict):
        return []
    results = output.get("result")
    if not isinstance(results, list):
        return []
    reactions = []
    for r in results:
        reaction = _reaction_of(r)
        if reaction:
            reactions.append(reaction)
    return reactions


def _reaction_of(result: dict[str, Any]) -> Reaction | None:
    """Extracts the reaction data from an ASKCOS result item."""
    if not isinstance(result, dict):
        return None
    outcome = result.get("outcome")
    if not isinstance(outcome, str):
        return None
    smiles = []
    for p in outcome.split("."):
        part = p.strip()
        if part != "":
            smiles.append(part)
    if len(smiles) == 0:
        return None
    score = result.get("average_model_score", 0.0)
    feasibility = 0.0
    props = result.get("reaction_properties")
    if isinstance(props, dict):
        feasibility = props.get("plausibility", 0.0)
    return Reaction(score, feasibility, smiles)


class AskcosClient(RetroClient):
    def __init__(
        self,
        config: AskcosConfig,
        model: AskcosModel = AskcosModel.PISTACHIO,
    ):
        self.session = requests.Session()
        self.endpoint = config.endpoint.strip().rstrip("/")
        self.model = model

        log.info("Requesting API token")
        resp = self.session.post(
            self._p("/admin/token"),
            data={
                "username": config.user,
                "password": config.password,
            },
        )
        resp.raise_for_status()

        payload: dict[str, Any] = resp.json()
        access_token = payload["access_token"]
        self.session.headers["Authorization"] = f"Bearer {access_token}"
        log.info("API token acquired successfully")

    def __enter__(self) -> "AskcosClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _p(self, segment: str) -> str:
        return self.endpoint + segment

    @override
    def expand(self, smiles: str) -> Res[list[Reaction]]:
        task_id, err = self._call(smiles)
        if err is not None:
            return chain_err(
                f"ASKCOS expansion request failed for {smiles}", err
            )

        assert task_id is not None
        reactions, err = self._poll(task_id)
        if err is not None:
            return chain_err(f"ASKCOS expansion failed for {smiles}", err)
        assert reactions is not None
        return reactions, nil

    def _call(self, smiles_code: str) -> Res[str]:
        log.info("Submitting retrosynthesis task for: %s", smiles_code)
        try:
            req = _request_of(smiles_code, self.model)
            response = self.session.post(
                self._p("/tree-search/expand-one/call-async"),
                params={"priority": 0},
                json=req,
            )
            response.raise_for_status()

            task_id = response.json()
            if not isinstance(task_id, str):
                return nil, f"Expected task ID string, got: {task_id!r}"

            log.info("Retrosynthesis task submitted: %s", task_id)
            return task_id, nil
        except Exception as err:
            return nil, str(err)

    def _poll(
        self,
        task_id: str,
        interval_seconds: float = 1.0,
        timeout_seconds: float = 300.0,
    ) -> Res[list[Reaction]]:
        task_url = self._p(f"/legacy/celery/task/{task_id}/")
        log.info("Polling task status at %s", task_url)

        started_at = time.monotonic()
        while True:
            try:
                resp = self.session.get(task_url)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            except Exception as err:
                return nil, str(err)

            if data.get("failed"):
                message = data.get("message", "no details available")
                return nil, f"Task {task_id} failed: {message}"

            if data.get("complete"):
                return _reactions_of(data), nil

            if time.monotonic() - started_at >= timeout_seconds:
                return nil, f"Timed out waiting for task {task_id}"
            time.sleep(interval_seconds)

    def close(self) -> str:
        log.info("Logging out via %s", self._p("/admin/logout"))
        resp = self.session.post(self._p("/admin/logout"))
        resp.raise_for_status()
        self.session.headers.pop("Authorization", None)
        log.info("Logout completed")
        self.session.close()
        return resp.text
