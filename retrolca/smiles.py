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
    mol = Chem.MolFromSmiles(smiles)  # ty: ignore
    if not mol:
        return smiles
    return Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)  # ty: ignore


def mol_weight(smiles: str) -> float | None:
    if not smiles or smiles == "":
        return None
    mol = Chem.MolFromSmiles(smiles)  # ty: ignore
    if not mol:
        return None
    return Descriptors.MolWt(mol)
