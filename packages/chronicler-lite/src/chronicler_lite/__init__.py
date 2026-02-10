"""Chronicler Lite — local-first storage and queue for Chronicler."""

from __future__ import annotations

from chronicler_lite.queue.sqlite_queue import SQLiteQueue

__all__ = ["MemVidStorage", "SQLiteQueue"]


def __getattr__(name: str):
    if name == "MemVidStorage":
        from chronicler_lite.storage.memvid_storage import MemVidStorage

        return MemVidStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
