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

A full example can be found [here](./examples/pubchem_decorate_flows.py)

### Retrosynthesis API

`retrolca` can build processes from different retrosynthesis APIs. At the
moment, the package supports ASKCOS and AiZynthFinder.

#### AiZynthFinder

For AiZynthFinder, install the project dependencies and download the public
model files into a local `models` folder.

```bash
# easy with uv; this will create a virtual environment with the dependencies
# AiZynthFinder comes with a script for downloading public models
uv sync
mkdir models
./.venv/bin/download_public_data models

# or on Windows
.\.venv\Scripts\download_public_data.exe models
```

The example in [examples/zynthfinder_example.py](examples/zynthfinder_example.py)
loads the generated `models/config.yml`, wraps it in `ZynthTool`, and passes
that tool to `ProcessBuilder`.

```python
import olca_ipc as ipc
import retrolca as retro

tool = retro.ZynthTool(Path("models/config.yml"))
ctx, _ = retro.IpcContext.of(ipc.Client())
builder = retro.ProcessBuilder(
	ctx,
	tool,
	category="Retrosynthesis/Inbox",
	max_levels=5,
	max_variants=2,
)
builder.build("CCCCN1CCCC1=O", "1-butylpyrrolidin-2-one")
```

#### ASKCOS

For ASKCOS, create a JSON config file with the API endpoint and login data.

```json
{
  "endpoint": "https://your-askcos-instance",
  "user": "your-user",
  "password": "your-password"
}
```

The example in [examples/askcos_example.py](examples/askcos_example.py) loads
that config, creates an `AskcosClient`, and uses it with `ProcessBuilder`.

```python

import olca_ipc as ipc
import retrolca as retro

config = retro.AskcosConfig.from_file(Path("auth/remote-askcos.json"))
ctx, _ = retro.IpcContext.of(ipc.Client())
with retro.AskcosClient(config) as client:
	builder = retro.ProcessBuilder(
		ctx,
		client,
		max_variants=2,
		max_levels=2,
		category="Retrosynthesis/Inbox",
	)
	builder.build("CCOP(=O)(OCC)OCC", name="triethyl phosphate")
```
