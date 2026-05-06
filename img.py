import askgen.zynth as z
import askgen.smiles as smiles

from rdkit import Chem
from rdkit.Chem import Draw


def main():
    config = z.ZynthConfig.from_file("auth/local-zynth.json")
    client = z.ZynthClient(config)
    product = "CCCCN1CCCC1=O"
    reaction = client.expand(product)[0]

    # +begin_src python
    codes = []
    for s in reaction.smiles:
        codes.append(s)
    codes.append(product)

    mols = [Chem.MolFromSmiles(s) for s in codes]

    names = []
    for c in codes:
        info = smiles.get_cirpy_info(c)
        name = info.name if info else c
        names.append(name)

    # Ein Gitter mit 4 Spalten erstellen
    img = Draw.MolsToGridImage(
        mols,
        molsPerRow=len(reaction.smiles),
        subImgSize=(200, 200),
        legends=names,
    )
    img.save("raster.png")  # Oder einfach im Notebook anzeigen
    # +end_src


if __name__ == "__main__":
    main()
