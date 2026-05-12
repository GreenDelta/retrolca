import logging
from pathlib import Path

import olca_ipc as ipc

import retrolca as zn


def main():
    logging.basicConfig(level=logging.INFO)
    config = Path(__file__).parent / "models/config.yml"
    tool = zn.ZynthTool(config)
    ctx, _ = zn.IpcContext.of(ipc.Client())
    assert ctx
    builder = zn.ProcessBuilder(
        ctx,
        tool,
        category="Retrosynthesis/Inbox",
        max_levels=5,
        max_variants=2,
    )
    builder.build("CCCCN1CCCC1=O", "1-butylpyrrolidin-2-one")


if __name__ == "__main__":
    main()
