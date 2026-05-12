from dataclasses import dataclass
from typing import Any

import requests
import olca_schema as o
from urllib.parse import quote

from . import oipc, smiles


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


def decorate_flow(ctx: oipc.IpcContext, flow: o.Flow) -> bool:
    if not ctx or not flow or not flow.name:
        return False
    pug = get_component(flow.name)
    if not pug:
        return False

    # add synonyms
    syns = set()
    syns.add(flow.name.strip().lower())
    if flow.synonyms:
        for s in flow.synonyms.split(";"):
            syns.add(s.strip().lower())
    for s in pug.synonyms():
        key = s.strip().lower()
        if key not in syns:
            if not flow.synonyms or flow.synonyms == "":
                flow.synonyms = s
            else:
                flow.synonyms += "; " + s

    # add additional properties
    if not flow.other_properties:
        flow.other_properties = {}
    props = [
        ("Connectivity-SMILES", pug.connectivity_smiles()),
        ("Absolute-SMILES", pug.absolute_smiles()),
        ("InChI-String", pug.inchi_string()),
        ("InChI-Key", pug.inchi_key()),
    ]
    for key, val in props:
        if not val:
            continue
        if flow.other_properties.get(key):
            continue
        flow.other_properties[key] = val

    # add the chemical amount if possible
    mm = ctx.molar_mass_of(flow)
    code = pug.absolute_smiles()
    if not mm and flow.flow_properties and code:
        mm = smiles.mol_weight(code)
        mass_prop = ctx.mass_prop_of(flow)
        if mm and mass_prop and mass_prop.is_ref_flow_property:
            flow.flow_properties.append(
                o.FlowPropertyFactor(
                    flow_property=ctx.chem_amount.to_ref(),
                    conversion_factor=1000 / mm,
                )
            )
        flow.other_properties["MolarMass"] = mm
    return True
