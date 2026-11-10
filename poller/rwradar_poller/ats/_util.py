"""Small helpers shared by the adapters."""

from __future__ import annotations

from typing import Any


def clean(value: Any) -> str:
    """Collapse whitespace; non-strings become ``""``."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def looks_remote(location: str) -> bool:
    return "remote" in location.lower()
