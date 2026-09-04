import copy
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

import requests

from .res import Res, chain_err, nil
from .tool import Reaction, RetroTool

log = logging.getLogger(__name__)


class AskcosModel:
    BKMS_METABOLIC = "bkms_metabolic"
    PISTACHIO = "pistachio"
    PISTACHIO_RINGBREAKER = "pistachio_ringbreaker"
    REAXYS = "reaxys"
    REAXYS_BIOCATALYSIS = "reaxys_biocatalysis"
    USPTO_HIGHER_LEVEL = "uspto_higher_level"


@dataclass
class AskcosLogin:
    endpoint: str
    user: str
    password: str

    @classmethod
    def from_file(cls, path: Path) -> "AskcosLogin":
        with open(path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)
            return AskcosLogin(**config)


def _model_name_of(options: dict[str, Any]) -> str:
    """Returns the retro model name from the given ASKCOS options.

    It returns 'reaxys' if no other model name was found, because
    this is the default model that is used in this case according
    to the ASKCOS API documentation.
    """
    retro = options.get("retro_backend_options")
    if isinstance(retro, dict):
        entries = [retro]
    elif isinstance(retro, list):
        entries = retro
    else:
        entries = []
    for entry in entries:
        if isinstance(entry, dict):
            name = entry.get("retro_model_name")
            if name:
                return str(name)
    return "reaxys"


def _set_model_in_options(options: dict[str, Any], model: str) -> None:
    """Writes retro_model_name into the retro_backend_options of options."""
    retro = options.get("retro_backend_options")
    if isinstance(retro, dict):
        retro["retro_model_name"] = model
        return

    if isinstance(retro, list):
        for entry in retro:
            if isinstance(entry, dict):
                entry["retro_model_name"] = model
                return
        retro.append({"retro_model_name": model})
        return

    options["retro_backend_options"] = [{"retro_model_name": model}]


def _request_object_of(
    smiles_code: str,
    model: str | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if options:
        obj = copy.deepcopy(options)
        obj["smiles"] = smiles_code
        if model:
            _set_model_in_options(obj, model)
        return obj

    retro_model = model or AskcosModel.PISTACHIO

    return {
        "smiles": smiles_code,
        "retro_backend_options": [
            {
                "retro_backend": "template_relevance",
                "max_num_templates": 1000,
                "max_cum_prob": 0.999,
                "retro_model_name": retro_model,
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


class AskcosClient(RetroTool):
    def __init__(
        self,
        config: AskcosLogin,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        self.session = requests.Session()
        self.endpoint = config.endpoint.strip().rstrip("/")

        # we include the model name into the ID because the ID
        # is used as cache-key for example and different models
        # give of course different results.
        if options is None:
            self.model = model if model else AskcosModel.PISTACHIO
            self.id = f"askcos-{self.model}"
            self.options = None
        else:
            # the full options take precedence for the actual request,
            # but an explicitly given model is injected into them at
            # request time (see _request_object_of). The ID reflects
            # that model so that cached results stay consistent.
            self.model = model
            self.options = options
            self.id = f"askcos-{model or _model_name_of(options)}"

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
            req = _request_object_of(smiles_code, self.model, self.options)
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
