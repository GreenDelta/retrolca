import logging as log
from dataclasses import dataclass
from typing import Any

import olca_ipc as ipc
import olca_schema as o

from . import smiles
from .res import Res, nil

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
    def load(client: ipc.IpcProtocol) -> Res["Context"]:
        mass = client.get(o.FlowProperty, _MASS_ID)
        if not mass:
            return nil, f"Flow property 'Mass' (id={_MASS_ID}) not found"
        if mass.name != "Mass":
            log.warning(
                "The name of the flow property '%s' (id=%s) should be 'Mass'",
                mass.name,
                _MASS_ID,
            )
        if not mass.unit_group or not mass.unit_group.id:
            return nil, "Flow property for 'Mass' does not link a unit group"

        mass_units = client.get(o.UnitGroup, mass.unit_group.id)
        if not mass_units or not mass_units.units:
            return nil, "No valid unit group for mass units found"
        kg = next((u for u in mass_units.units if u.name == "kg"), None)
        if not kg or not kg.is_ref_unit:
            return nil, "'kg' is not the reference unit of mass"

        chem_amount = client.get(o.FlowProperty, _CHEMICAL_AMOUNT_ID)
        if not chem_amount:
            return nil, (
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
            return nil, (
                "Flow property for 'Chemical amount' does not link a unit group"
            )
        chem_amount_units = client.get(o.UnitGroup, chem_amount.unit_group.id)
        if not chem_amount_units or not chem_amount_units.units:
            return nil, "No valid unit group for chemical amount units found"
        mole = next(
            (u for u in chem_amount_units.units if u.name == "mol"), None
        )
        if not mole or not mole.is_ref_unit:
            return nil, "'mol' is not the reference unit of chemical amount"

        return (
            Context(
                client=client,
                mass=mass,
                chem_amount=chem_amount,
                kg=kg,
                mole=mole,
            ),
            nil,
        )


    def molar_mass_of(self, flow: o.Flow) -> float | None:
        """Returns the molar mass in g/mol of the flow for this context.

        Returns ``None`` if the respective flow properties for mass and chemical
        amount are not defined in the flow.
        """
        if not flow or not flow.flow_properties:
            return None
        mass_prop: o.FlowPropertyFactor | None = None
        chem_prop: o.FlowPropertyFactor | None = None
        for prop in flow.flow_properties:
            if not prop.flow_property:
                continue
            if prop.flow_property.id == self.mass.id:
                mass_prop = prop
                continue
            if prop.flow_property.id == self.chem_amount.id:
                chem_prop = prop
                continue
        if not mass_prop or not chem_prop:
            return None

        if mass_prop.is_ref_flow_property:
            return 1000 / chem_prop.conversion_factor
        if chem_prop.is_ref_flow_property:
            return 1000 * mass_prop.conversion_factor
        return None


@dataclass
class FlowIndex:
    data: dict[str, o.Flow]

    @staticmethod
    def load(ctx: Context):
        log.info(
            "Build index of chemical products in openLCA with SMILES codes"
        )
        data = {}
        for flow in ctx.client.get_all(o.Flow):
            code = smiles.of_flow(flow)
            if not code:
                continue
            mm = ctx.molar_mass_of(flow)
            if not mm:
                continue
            data[code] = flow
        log.info("Created index with %d chemical products", len(data))
        return FlowIndex(data)


def create_product(
    ctx: Context,
    smiles_code: str,
    name: str | None = None,
    category: str | None = None,
) -> Res[o.Flow]:
    # a name of the product is required
    # either it is given or we get it from CIRpy
    info = smiles.get_cirpy_info(smiles_code)
    product: str
    if name:
        product = name
    elif info:
        product = info.name  # type: ignore
    else:
        product = smiles_code

    flow = o.new_product(product, ctx.mass)
    if not flow or not flow.flow_properties:
        return nil, "Could not create product flow"
    flow.category = category
    flow.description = (
        "This product flow was automatically generated from it's SMILES code. "
        "See also see the additional properties of the flow for more "
        "information."
    )

    # add the chemical amount as flow property
    mw = smiles.mol_weight(smiles_code)
    if mw <= 0:
        return nil, f"Could not calculate the molar mass of: {smiles_code}"
    flow.flow_properties.append(
        o.FlowPropertyFactor(
            conversion_factor=1000 / mw, flow_property=ctx.chem_amount.to_ref()
        )
    )

    # additional properties
    props: dict[str, Any] = {}
    flow.other_properties = props
    props["SMILES"] = smiles_code
    props["MolarMass"] = mw
    if info:
        flow.formula = info.formula
        if info.inchi:
            props["InChI-String"] = info.inchi
        if info.inchi_key:
            props["InChI-Key"] = info.inchi_key

    ctx.client.put(flow)
    return flow, nil
