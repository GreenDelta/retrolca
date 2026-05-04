from dataclasses import dataclass
from typing import Any

import requests
from urllib.parse import quote


@dataclass()
class UrnValue:
    urn: dict[str, Any]
    value: dict[str, Any]

    @property
    def label(self) -> str | None:
        return self.urn.get("label")

    @property
    def name(self) -> str | None:
        return self.urn.get("name")

    @property
    def value(self) -> str | None:
        return self.value.get("sval")

@dataclass
class PugComponent:
    data: dict[str, Any]

    def props(self) -> list[UrnValue]:
        ps = self.data.get("props")
        if not isinstance(ps, list):
            return []
        props = []
        for p in ps:
            if not isinstance(p, dict):
                continue
            urn = p.get("urn")
            value = p.get("value")
            if isinstance(urn, dict) and isinstance(value, dict):
                props.append(UrnValue(urn, value))
        return props


def get_for_name(name: str) -> PugComponent | None:
    n = quote(name)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{n}/JSON"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not isinstance(data, dict):
        return None
    compounds = data.get("PC_Compounds")
    if not isinstance(compounds, list):
        return None
    if len(compounds) == 0:
        return None
    first = compounds[0]
    if isinstance(first, dict):
        return PugComponent(first)
    else:
        return None


if __name__ == '__main__':
    obj = get_for_name("1-(N,N-Bis(2-ethylhexyl)aminomethyl)-4-methylbenzotriazole")
    print(obj)
