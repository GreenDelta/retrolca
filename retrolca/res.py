"""Minimal Go-style result types.

This module models expected failures as ordinary return values instead of
exceptions. Functions return either a value and ``nil`` for the error, or
``nil`` for the value and an error message.
"""

from typing import TypeVar, Optional

type Res[T] = tuple[T, None] | tuple[None, str]
"""A result pair of ``(value, nil)`` or ``(nil, error_message)``."""

nil = None
"""A shorter name for ``None``, like in Go."""


def chain_err(msg: str, err: str) -> tuple[None, str]:
    """Prefix an error with context."""
    return nil, f"{msg}\n  -> {err}"


T = TypeVar("T")


def unwrap(value: Optional[T], error_message="Required value is missing") -> T:
    if value is None:
        raise ValueError(error_message)
    return value
