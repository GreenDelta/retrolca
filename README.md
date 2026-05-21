# retrolca

`retrolca` is a project for transforming retrosynthesis pathways into openLCA process datasets.

## Usage

### Requirements

To build processes from a retrosynthesis API, you first need an openLCA
database with chemical product flows that are decorated with SMILES codes.
The package contains tooling that can enrich a database with data from
PubChem.

```python
import olca_ipc as ipc
import retrolca as retro
import retrolca.pubchem as pub

client = ipc.Client()
ctx, _ = retro.IpcContext.of(client)
pub.IpcFlowDecorator(ctx).try_all(in_path="manufacture of basic chemicals")
```

Once a database is decorated, you can persist the collected PubChem
decorations to JSON and later apply them to another database.

```python
pub.dump_decorations(ctx, path)
pub.load_decorations(ctx, path)
```


## Building blocks

### Retrosynthesis API

#### AiZynthFinder

```bash
# make sure a virtual environment exists with the AiZynthFinder tools
uv sync
# download the public default modles to the ./models folder
mkdir models
./.venv/bin/download_public_data models
```
