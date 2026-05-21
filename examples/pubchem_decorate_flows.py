import logging as log
from pathlib import Path

import olca_ipc as ipc

import retrolca as retro
import retrolca.pubchem as pub

DUMP = Path(__file__).parent.parent / "out/pubchem_deco.json"


def main():
    log.basicConfig(level=log.INFO)

    # load the IPC context
    client = ipc.Client()
    ctx, err = retro.IpcContext.of(client)
    if err:
        print(f"Failed to load context: {err}")
        return
    assert ctx

    if DUMP.exists():
        pub.load_decorations(ctx, DUMP)
        return

    pub.IpcFlowDecorator(ctx).try_all(in_path="manufacture of basic chemicals")
    pub.dump_decorations(ctx, DUMP)


if __name__ == "__main__":
    main()
