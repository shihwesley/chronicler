"""Storage backends for Chronicler Lite."""

from __future__ import annotations

__all__ = ["MemVidStorage"]


def __getattr__(name: str):
    if name == "MemVidStorage":
        from chronicler_lite.storage.memvid_storage import MemVidStorage

        return MemVidStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
