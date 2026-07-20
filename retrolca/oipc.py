import logging as log
from dataclasses import dataclass
from typing import cast

import olca_ipc as ipc
import olca_schema as o

from . import smiles
from .res import Res, nil, unwrap

# The official openLCA IDs of the quantity types 'mass' and 'chemical amount'.
# see https://github.com/GreenDelta/data/blob/master/refdata/flow_properties.csv
_MASS_ID = "93a60a56-a3c8-11da-a746-0800200b9a66"
_CHEMICAL_AMOUNT_ID = "341fd786-b2ad-4552-a762-5eafcab45dee"


@dataclass
class IpcContext:
    client: ipc.ProtoClient
    mass: o.FlowProperty
    chem_amount: o.FlowProperty
    kg: o.Unit
    mole: o.Unit

    @staticmethod
    def of(client: ipc.ProtoClient) -> Res["IpcContext"]:
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
            IpcContext(
                client=client,
                mass=mass,
                chem_amount=chem_amount,
                kg=kg,
                mole=mole,
            ),
            nil,
        )

    def mass_prop_of(self, flow: o.Flow) -> o.FlowPropertyFactor | None:
        if not flow or not flow.flow_properties:
            return None
        for f in flow.flow_properties:
            if f.flow_property and f.flow_property.id == self.mass.id:
                return f
        return None

    def chem_prop_of(self, flow: o.Flow) -> o.FlowPropertyFactor | None:
        if not flow or not flow.flow_properties:
            return None
        for f in flow.flow_properties:
            if f.flow_property and f.flow_property.id == self.chem_amount.id:
                return f
        return None

    def molar_mass_of(self, flow: o.Flow | o.Ref) -> float | None:
        """Returns the molar mass in g/mol of the flow for this context.

        Returns ``None`` if the respective flow properties for mass and chemical
        amount are not defined in the flow.
        """
        if not flow:
            return None
        if isinstance(flow, o.Ref):
            f = self.client.get(o.Flow, flow.id)
            if not f:
                return None
            flow = f
        if not flow.flow_properties:
            return None

        mass_prop = self.mass_prop_of(flow)
        chem_prop = self.chem_prop_of(flow)
        if not mass_prop or not chem_prop:
            return None
        if mass_prop.is_ref_flow_property:
            return 1000 / cast(float, chem_prop.conversion_factor)
        if chem_prop.is_ref_flow_property:
            return 1000 * cast(float, mass_prop.conversion_factor)
        return None


@dataclass
class FlowIndex:
    data: dict[str, o.Flow]

    @staticmethod
    def of(ctx: IpcContext) -> "FlowIndex":
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


@dataclass
class ProviderIndex:
    data: dict[str, o.TechFlow]

    @classmethod
    def of(cls, ctx: IpcContext, preferred_location="GLO") -> "ProviderIndex":
        data = {}
        provider_idx = cls.__index_providers(ctx.client)
        for flow in ctx.client.get_all(o.Flow):
            smiles_code = smiles.of_flow(flow)
            if not smiles_code:
                continue
            mm = ctx.molar_mass_of(flow)
            if not mm:
                continue
            providers = provider_idx.get(unwrap(flow.id))
            if not providers:
                continue

            score = 0
            provider: o.TechFlow | None = None
            for p in providers:
                if not provider:
                    provider = p
                    score = cls.__score_of(p, preferred_location)
                    continue
                s = cls.__score_of(p, preferred_location)
                if s > score:
                    provider = p
                    score = s
            if provider:
                data[smiles_code] = provider
        return cls(data)

    @staticmethod
    def __index_providers(
        client: ipc.ProtoClient,
    ) -> dict[str, list[o.TechFlow]]:
        provider_idx = {}
        for p in client.get_providers():
            if not p.flow or not p.flow.id:
                continue
            ps = provider_idx.get(p.flow.id)
            if not ps:
                ps = []
                provider_idx[p.flow.id] = ps
            ps.append(p)
        return provider_idx

    @staticmethod
    def __score_of(p: o.TechFlow, location: str) -> float:
        if not p or not p.flow or not p.provider:
            return 0.0
        score = 0.0
        if p.flow.name and p.provider.name:
            market_prefix = "market for " + p.flow.name
            prod_prefix = p.flow.name + " production"
            if p.provider.name.startswith(market_prefix):
                score += 8
            elif p.provider.name.startswith(prod_prefix):
                score += 5

        if p.provider.location:
            if p.provider.location == location:
                score += 10
            elif p.provider.location == "GLO":
                score += 5
            elif p.provider.location == "RoW":
                score += 2
        return score

    def get(self, smiles_code: str) -> o.TechFlow | None:
        return self.data.get(smiles_code)

    def put(self, smiles_code: str, process: o.Process) -> o.TechFlow:
        flow_ref: o.Ref | None = None
        for e in unwrap(process.exchanges):
            if e.is_quantitative_reference:
                flow_ref = e.flow
                break
        provider = o.TechFlow(flow=flow_ref, provider=process.to_ref())
        self.data[smiles_code] = provider
        return provider
