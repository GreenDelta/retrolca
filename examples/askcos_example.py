import logging as log
from pathlib import Path

import olca_ipc as ipc

import retrolca as retro


def main():
    log.basicConfig(
        level=log.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    config = retro.AskcosConfig.from_file(
        Path(__file__).parent.parent / "auth/remote-askcos.json"
    )

    ctx, err = retro.IpcContext.of(ipc.Client())
    assert ctx, err

    with retro.AskcosClient(config) as client:
        builder = retro.ProcessBuilder(
            ctx,
            client,
            max_variants=2,
            max_levels=2,
            category="Retrosynthesis/Inbox",
        )
        builder.build("CCOP(=O)(OCC)OCC", name="triethyl phosphate")


if __name__ == "__main__":
    main()
