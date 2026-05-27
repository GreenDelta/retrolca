from dataclasses import dataclass
from typing import Any, Protocol, override

import cirpy


@dataclass
class NamingInfo:
    name: str
    smiles: str
    formula: str | None
    inchi: str | None
    inchi_key: str | None


class NamingService(Protocol):
    id: str

    def get_info(self, smiles: str) -> NamingInfo | None: ...

    def get_name(self, smiles: str) -> str:
        """Returns the name for the given SMILES code.

        It returns the SMILES code if the lookup did not return a result.
        """
        info = self.get_info(smiles)
        return info.name if info else smiles


class CIR(NamingService):
    def __init__(self):
        self.id = "CIR"

    @override
    def get_info(self, smiles: str) -> NamingInfo | None:
        mol = cirpy.Molecule(smiles)
        if not mol or not isinstance(mol.iupac_name, str):
            return None
        return NamingInfo(
            name=mol.iupac_name.lower() if mol.iupac_name else smiles,
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
