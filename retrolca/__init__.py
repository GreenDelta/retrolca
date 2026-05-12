import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)


@dataclass
class RetroBackendOption:
    retro_backend: str = "template_relevance"
    max_num_templates: int = 1000
    max_cum_prob: float = 0.999
    retro_model_name: str = "reaxys"


@dataclass
class RetroRequest:
    smiles: str
    retro_backend_options: list[RetroBackendOption] = field(
        default_factory=lambda: [RetroBackendOption()]
    )
    retro_rerank_backend: str = "relevance_heuristic"
    atom_map_backend: str = "rxnmapper"
    use_fast_filter: bool = True
    fast_filter_threshold: float = 0.1
    cluster_precursors: bool = False

    @classmethod
    def of(
        cls,
        smiles: str,
        retro_backend_options: list[RetroBackendOption] | None = None,
        retro_rerank_backend: str = "relevance_heuristic",
        atom_map_backend: str = "rxnmapper",
        use_fast_filter: bool = True,
        fast_filter_threshold: float = 0.1,
        cluster_precursors: bool = False,
    ) -> "RetroRequest":
        return cls(
            smiles=smiles,
            retro_backend_options=retro_backend_options
            if retro_backend_options is not None
            else [RetroBackendOption()],
            retro_rerank_backend=retro_rerank_backend,
            atom_map_backend=atom_map_backend,
            use_fast_filter=use_fast_filter,
            fast_filter_threshold=fast_filter_threshold,
            cluster_precursors=cluster_precursors,
        )

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Auth:
    endpoint: str
    user: str
    password: str

    @staticmethod
    def read(path: str | Path) -> "Auth":
        log.info("Loading auth config from %s", path)
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return Auth(
                data["endpoint"],
                data["user"],
                data["password"],
            )

    def write(self, path: str | Path) -> None:
        log.info("Writing auth config to %s", path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f)


class RetroResult:
    def __init__(self, data: dict[str, Any]):
        self.data = data if data else {}

    @property
    def score(self) -> float:
        return self.data.get("average_model_score", 0.0)

    @property
    def outcome(self) -> list[str]:
        out = self.data.get("outcome")
        if not isinstance(out, str):
            return []
        smiles = []
        for part in out.split("."):
            if part != "":
                smiles.append(part)
        return smiles


class RetroResponse:
    def __init__(self, data: dict[str, Any]):
        self.data = data if data else {}

    @property
    def results(self) -> list[RetroResult]:
        res = self.data.get("result")
        if not isinstance(res, list):
            return []
        items = []
        for d in res:
            if isinstance(d, dict):
                items.append(RetroResult(d))
        return items


class Client:
    def __init__(self, auth: Auth):
        self.auth = auth
        self.session = requests.Session()
        self.endpoint = auth.endpoint.strip().rstrip("/")
        log.info("Initialized ASKCOS client for %s", self.endpoint)

    def _p(self, segment: str) -> str:
        return self.endpoint + segment

    def login(self) -> str:
        log.info("Requesting API token from %s", self._p("/admin/token"))
        response = self.session.post(
            self._p("/admin/token"),
            data={
                "username": self.auth.user,
                "password": self.auth.password,
            },
        )
        response.raise_for_status()

        payload: dict[str, Any] = response.json()
        access_token = payload["access_token"]
        self.session.headers["Authorization"] = f"Bearer {access_token}"
        log.info("API token acquired successfully")
        return access_token

    def run(self, request: RetroRequest, priority: int = 0) -> str:
        log.info(
            "Submitting retrosynthesis task to %s with priority=%s",
            self._p("/tree-search/expand-one/call-async"),
            priority,
        )
        response = self.session.post(
            self._p("/tree-search/expand-one/call-async"),
            params={"priority": priority},
            json=request.payload(),
        )
        response.raise_for_status()

        task_id = response.json()
        if not isinstance(task_id, str):
            raise ValueError(f"Expected task ID string, got: {task_id!r}")

        log.info("Retrosynthesis task submitted: %s", task_id)
        return task_id

    def poll(
        self,
        task_id: str,
        interval_seconds: float = 1.0,
        timeout_seconds: float = 300.0,
    ) -> RetroResponse:
        task_url = self._p(f"/legacy/celery/task/{task_id}/")
        log.info("Polling task status at %s", task_url)

        started_at = time.monotonic()
        while True:
            response = self.session.get(task_url)
            response.raise_for_status()

            payload: dict[str, Any] = response.json()
            state = payload.get("state", "UNKNOWN")
            percent = payload.get("percent")
            message = payload.get("message", "")
            log.info(
                "Task %s state=%s percent=%s message=%s",
                task_id,
                state,
                percent,
                message,
            )

            if payload.get("failed"):
                raise RuntimeError(f"Task {task_id} failed: {message}")

            if payload.get("complete"):
                output = payload.get("output")
                if not isinstance(output, dict):
                    raise ValueError(
                        f"Task {task_id} completed without output: {payload!r}"
                    )
                log.info("Task %s completed successfully", task_id)
                return RetroResponse(output)

            if time.monotonic() - started_at >= timeout_seconds:
                raise TimeoutError(f"Timed out waiting for task {task_id}")

            time.sleep(interval_seconds)

    def logout(self) -> str:
        log.info("Logging out via %s", self._p("/admin/logout"))
        response = self.session.post(self._p("/admin/logout"))
        response.raise_for_status()
        self.session.headers.pop("Authorization", None)
        log.info("Logout completed")
        return response.text
