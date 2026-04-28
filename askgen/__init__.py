import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class Auth:
    endpoint: str
    user: str
    password: str

    @staticmethod
    def read(path: str | Path) -> "Auth":
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return Auth(
                data["endpoint"],
                data["user"],
                data["password"],
            )

    def write(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f)


class Askcos:
    def __init__(self, auth: Auth):
        self.auth = auth
        self.session = requests.Session()
        self.endpoint = auth.endpoint.strip().rstrip("/")

    def _p(self, segment: str) -> str:
        return self.endpoint + segment

    def login(self) -> Auth:
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
        return access_token

    def logout(self) -> str:
        response = self.session.post(self._p("/admin/logout"))
        response.raise_for_status()
        self.session.headers.pop("Authorization", None)
        return response.text
