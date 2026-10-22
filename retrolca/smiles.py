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


def reaction_smiles(reactants: list[str], product: str) -> str:
    """Returns a stable reaction SMILES key for the given reaction.

    The key follows the reaction SMILES standard
    ``reactants>agents>products`` with an empty agents section. The reactants
    are canonicalized and sorted so that the key does not depend on the order
    in which a retrosynthesis tool returns them.
    """
    codes = [canonicalize(code) for code in reactants]
    codes = sorted(code for code in codes if code)
    return f"{'.'.join(codes)}>>{canonicalize(product)}"


def mol_weight(smiles: str) -> float | None:
    if not smiles or smiles == "":
        return None
    mol = Chem.MolFromSmiles(smiles)  # ty: ignore
    if not mol:
        return None
    return Descriptors.MolWt(mol)
