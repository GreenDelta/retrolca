import logging as log
from pathlib import Path

import olca_ipc as ipc

import retrolca as retro


def main():
    log.basicConfig(
        level=log.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    login = retro.AskcosLogin.from_file(
        Path(__file__).parent.parent / "auth/remote-askcos.json"
    )

    ctx, err = retro.IpcContext.of(ipc.Client())
    assert ctx, err

    with retro.AskcosClient(login) as tool:
        builder = retro.ProcessBuilder(
            ctx,
            tool,
            max_variants=2,
            max_levels=2,
        )
        builder.build(
            "CCOP(=O)(OCC)OCC",
            name="triethyl phosphate",
            category="ASKCOS/Inbox",
        )


if __name__ == "__main__":
    main()
