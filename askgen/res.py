type Res[T] = tuple[T, None] | tuple[None, str]
nil = None


def chain_err(msg: str, err: str) -> tuple[None, str]:
    return nil, f"{msg}\n  -> {err}"
