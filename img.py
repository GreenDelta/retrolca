import base64
import io

import olca_ipc as ipc
import olca_schema as o
from rdkit import Chem
from rdkit.Chem import Draw

import retrolca.smiles as smiles
import retrolca.zynth as z


def main():
    config = z.ZynthConfig.from_file("auth/local-zynth.json")
    client = z.ZynthClient(config)
    product = "CCCCN1CCCC1=O"
    reactions, err = client.expand(product)
    if err:
        raise RuntimeError(err)
    assert reactions is not None
    reaction = reactions[0]

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

    img = Draw.MolsToGridImage(
        mols,
        molsPerRow=len(reaction.smiles),
        subImgSize=(200, 200),
        legends=names,
    )
    # img.save("raster.png")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    img_str = base64.b64encode(buffer.getvalue()).decode("ascii")
    print(img_str)

    client = ipc.Client()
    source = o.Source(name="Some example with image", category="Inbox")
    client.put(source)
    file_data = ipc.FileData("reaction.png", img_str)
    client.put_source_file(source, file_data)

    data = base64.b64decode(img_str)
    with open("out/b64.png", "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
