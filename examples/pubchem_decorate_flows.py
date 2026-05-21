import logging as log

import olca_ipc as ipc

import retrolca as retro
from retrolca.pubchem import IpcFlowDecorator


def main():
    log.basicConfig(level=log.INFO)
    client = ipc.Client()
    ctx, err = retro.IpcContext.of(client)
    if err:
        print(f"Failed to load context: {err}")
        return
    assert ctx
    IpcFlowDecorator(ctx).try_all(in_path="manufacture of basic chemicals")


if __name__ == "__main__":
    main()
