import logging as log
from dataclasses import dataclass

import olca_ipc as ipc
import olca_schema as o

# The official openLCA IDs of the quantity types 'mass' and 'chemical amount'.
# see https://github.com/GreenDelta/data/blob/master/refdata/flow_properties.csv
_MASS_ID = "93a60a56-a3c8-11da-a746-0800200b9a66"
_CHEMICAL_AMOUNT_ID = "341fd786-b2ad-4552-a762-5eafcab45dee"


@dataclass
class Context:
    client: ipc.IpcProtocol
    mass: o.FlowProperty
    chem_amount: o.FlowProperty
    kg: o.Unit
    mole: o.Unit

    @staticmethod
    def load(client: ipc.IpcProtocol):
        mass = client.get(o.FlowProperty, _MASS_ID)
        if not mass:
            raise Exception(f"Flow property 'Mass' (id={_MASS_ID}) not found")
        if mass.name != "Mass":
            log.warning(
                "The name of the flow property '%s' (id=%s) should be 'Mass'",
                mass.name,
                _MASS_ID,
            )
        if not mass.unit_group or not mass.unit_group.id:
            raise Exception(
                "Flow property for 'Mass' does not link a unit group"
            )

        mass_units = client.get(o.UnitGroup, mass.unit_group.id)
        if not mass_units or not mass_units.units:
            raise Exception("No valid unit group for mass units found")
        kg = next((u for u in mass_units.units if u.name == "kg"), None)
        if not kg or not kg.is_ref_unit:
            raise Exception("'kg' is not the reference unit of mass")

        chem_amount = client.get(o.FlowProperty, _CHEMICAL_AMOUNT_ID)
        if not chem_amount:
            raise Exception(
                f"Flow property 'Chemical amount' (id={_CHEMICAL_AMOUNT_ID}) "
                f"not found"
            )
        if chem_amount.name != "Chemical amount":
            log.warning(
                "The name of the flow property '%s' (id=%s) should be "
                "'Chemical amount'",
                chem_amount.name,
                _CHEMICAL_AMOUNT_ID,
            )
        if not chem_amount.unit_group or not chem_amount.unit_group.id:
            raise Exception(
                "Flow property for 'Chemical amount' does not link a unit group"
            )
        chem_amount_units = client.get(o.UnitGroup, chem_amount.unit_group.id)
        if not chem_amount_units or not chem_amount_units.units:
            raise Exception(
                "No valid unit group for chemical amount units found"
            )
        mole = next(
            (u for u in chem_amount_units.units if u.name == "mol"), None
        )
        if not mole or not mole.is_ref_unit:
            raise Exception(
                "'mol' is not the reference unit of chemical amount"
            )

        return Context(
            client=client,
            mass=mass,
            chem_amount=chem_amount,
            kg=kg,
            mole=mole,
        )
