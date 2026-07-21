import logging
from pathlib import Path

import olca_ipc as ipc

import retrolca as zn


def main():
    logging.basicConfig(level=logging.INFO)
    config = Path(__file__).parent.parent / "models/config.yml"
    tool = zn.ZynthTool(config)
    ctx, _ = zn.IpcContext.of(ipc.Client())
    assert ctx
    builder = zn.ProcessBuilder(
        ctx,
        tool,
        max_levels=2,
        max_variants=1,
        gen_process="83083965-4104-4c87-88af-bc200b6a520c",
        bal_process="4ad86534-aba4-3106-ac12-81e322834704",
    )
    builder.expand_process(
        "c74ccb59-b79a-4d51-8df0-33f7320f4b53",
        category="Retrosynthesis/Inbox",
    )


if __name__ == "__main__":
    main()
