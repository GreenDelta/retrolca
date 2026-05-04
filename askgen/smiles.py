import uuid
from dataclasses import dataclass
from typing import Any

import cirpy
import olca_schema as o

from rdkit import Chem
from rdkit.Chem import Descriptors


@dataclass
class CirpyInfo:
    name: str
    smiles: str
    formula: str | None
    inchi: str | None
    inchi_key: str | None


def get_cirpy_info(smiles: str) -> CirpyInfo | None:
    mol = cirpy.Molecule(smiles)
    if not mol or not isinstance(mol.iupac_name, str):
        return None
    return CirpyInfo(
        name=mol.iupac_name,
        smiles=smiles,
        formula=_str(mol.formula),
        inchi=_str(mol.stdinchi),
        inchi_key=_str(mol.stdinchikey),
    )


def _str(v: Any) -> str | None:
    if isinstance(v, str):
        return v
    else:
        return None


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
