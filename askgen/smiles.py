import uuid

import olca_schema as o

from rdkit import Chem
from rdkit.Chem import Descriptors


def of_flow(flow: o.Flow) -> str | None:
    if not flow or not flow.other_properties:
        return None
    smiles = flow.other_properties.get("SMILES")
    if not smiles:
        smiles = flow.other_properties.get("Absolute-SMILES")
    if not smiles:
        smiles = flow.other_properties.get("Connectivity-SMILES")
    if not isinstance(smiles, str):
        return None
    return canonicalize(smiles)


def canonicalize(smiles: str) -> str:
    if not smiles or smiles == "":
        return ""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return smiles
    return Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)


def mol_weight(smiles: str) -> float:
    if not smiles or smiles == "":
        return 0.0
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return 0
    return Descriptors.MolWt(mol)


def as_uid(smiles: str) -> str:
    uid = uuid.uuid5(uuid.NAMESPACE_OID, smiles)
    return str(uid)
