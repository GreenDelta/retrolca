import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from urllib.parse import quote


@dataclass()
class UrnValue:
    urn_data: dict[str, Any]
    value_data: dict[str, Any]

    @property
    def label(self) -> str | None:
        return self.urn_data.get("label")

    @property
    def name(self) -> str | None:
        return self.urn_data.get("name")

    @property
    def value(self) -> str | None:
        return self.value_data.get("sval")


@dataclass
class PugComponent:
    data: dict[str, Any]
    props: list[UrnValue]

    @staticmethod
    def of(data: dict[str, Any]) -> "PugComponent":
        if not data:
            return PugComponent({}, [])
        ps = data.get("props")
        if not isinstance(ps, list):
            return PugComponent(data, [])
        props = []
        for p in ps:
            if not isinstance(p, dict):
                continue
            urn = p.get("urn")
            value = p.get("value")
            if isinstance(urn, dict) and isinstance(value, dict):
                props.append(UrnValue(urn, value))
        return PugComponent(data, props)

    def synonyms(self) -> set[str]:
        syns = set()
        for prop in self.props:
            if prop.label == "IUPAC Name":
                if v := prop.value:
                    syns.add(v)
        return syns

    def absolute_smiles(self) -> str | None:
        return self.__v("SMILES", "Absolute")

    def connectivity_smiles(self) -> str | None:
        return self.__v("SMILES", "Connectivity")

    def inchi_string(self) -> str | None:
        return self.__v("InChI", "Standard")

    def inchi_key(self) -> str | None:
        return self.__v("InChIKey", "Standard")

    def molar_mass(self) -> float | None:
        m = self.__v("Molecular Weight", None)
        if not m:
            m = self.__v("Mass", "Exact")
        if not m:
            m = self.__v("Weight", "MonoIsotopic")
        if m:
            return float(m)
        else:
            return None

    def __v(self, label: str, name: str | None) -> str | None:
        for prop in self.props:
            if prop.label == label and prop.name == name:
                return prop.value
        return None


def get_component(name: str) -> PugComponent | None:
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
        return PugComponent.of(first)
    else:
        return None


ROOT = Path(__file__).parent.parent


def w_example():
    obj = get_component(
        "1-(N,N-Bis(2-ethylhexyl)aminomethyl)-4-methylbenzotriazole"
    )
    with open(ROOT / "out/pug.json", "w", encoding="utf-8") as f:
        json.dump(obj.data, f)
    print(obj)


if __name__ == "__main__":
    with open(ROOT / "out/pug.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        pug = PugComponent.of(data)
        print(pug.synonyms())
        print(pug.molar_mass())
