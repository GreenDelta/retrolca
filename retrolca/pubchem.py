import datetime
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import olca_schema as o
import requests

from . import oipc, smiles


log = logging.getLogger(__name__)


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


class IpcFlowDecorator:
    def __init__(self, ctx: oipc.IpcContext):
        self.ctx = ctx

    def try_all(
        self, in_path="manufacture of basic chemicals", request_interval=0.3
    ):
        """Try to decorate all matching product flows with information from PubChem."""

        # search for matching chemical products
        flows: list[o.Flow] = []
        for flow in self.ctx.client.get_all(o.Flow):
            if self.should_try(flow, in_path):
                flows.append(flow)
        n = len(flows)
        if n == 0:
            log.info("No untagged chemical products found")
            return
        log.info("Found %s chemical products to test", n)

        i = 0
        for flow in flows:
            i += 1
            # try to add attributes from PubChem
            log.info("%s (%s) ... [%s/%s]", flow.name, flow.id, i, n)
            b = self.try_with(flow)
            if b:
                log.info("  ... updated")
            else:
                log.info("  ... not found on PubChem")

            # mark the flow as checked and update it
            if not flow.other_properties:
                flow.other_properties = {}
            timestamp = datetime.datetime.now().isoformat()
            flow.other_properties["PubChem-Check"] = timestamp
            flow.last_change = timestamp
            flow.version = self._increment_version(flow.version)
            self.ctx.client.put(flow)

            time.sleep(request_interval)

    def try_with(self, flow: o.Flow) -> bool:
        """Try to decorate the given flow with information from PubChem.
        Returns `True`, when it found the flow by name on PubChem and updated it.
        """
        if not flow or not flow.name:
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
        mm = self.ctx.molar_mass_of(flow)
        code = pug.absolute_smiles()
        if not mm and flow.flow_properties and code:
            mm = smiles.mol_weight(code)
            mass_prop = self.ctx.mass_prop_of(flow)
            if mm and mass_prop and mass_prop.is_ref_flow_property:
                flow.flow_properties.append(
                    o.FlowPropertyFactor(
                        flow_property=self.ctx.chem_amount.to_ref(),
                        conversion_factor=1000 / mm,
                    )
                )
            flow.other_properties["MolarMass"] = mm
        return True

    def should_try(
        self, flow: o.Flow, in_path="manufacture of basic chemicals"
    ) -> bool:
        # only try product flows with a category and name given
        if not flow or flow.flow_type != o.FlowType.PRODUCT_FLOW:
            return False
        if not flow.category or not flow.name:
            return False

        # we identify chemicals by their category
        path = flow.category.lower()
        if in_path not in path:
            return False

        # check if the flow is already suitable for retrosynthesis
        code = smiles.of_flow(flow)
        mm = self.ctx.molar_mass_of(flow)
        if code and mm:
            return False

        # ignore when the flow was already checked
        if flow.other_properties:
            state = flow.other_properties.get("PubChem-Check")
            if state:
                return False

        # mass has to be the reference flow property
        mass_prop = self.ctx.mass_prop_of(flow)
        if not mass_prop or not mass_prop.is_ref_flow_property:
            return False

        return True

    def _increment_version(self, v: str | None) -> str:
        if not v:
            return "0.0.1"
        parts = []
        for si in v.split("."):
            vi = si.strip()
            if vi == "":
                parts.append(0)
            else:
                parts.append(int(vi))
        if len(parts) == 0:
            return "0.0.1"
        parts[-1] = parts[-1] + 1
        return ".".join([str(i) for i in parts])
