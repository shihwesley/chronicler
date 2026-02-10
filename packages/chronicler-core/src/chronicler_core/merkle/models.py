"""Data models for the Merkle tree subsystem."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEX12_RE = re.compile(r"[a-f0-9]{12}")


@dataclass(frozen=True)
class MerkleNode:
    """A node in the Merkle tree, representing either a file or directory."""

    path: str
    hash: str
    children: tuple[str, ...] = ()
    source_hash: str | None = None
    doc_hash: str | None = None
    doc_path: str | None = None
    stale: bool = False

    def __post_init__(self) -> None:
        if not _HEX12_RE.fullmatch(self.hash):
            raise ValueError(f"hash must be 12-char hex, got {self.hash!r}")


@dataclass(frozen=True)
class MerkleDiff:
    """Result of comparing two Merkle trees."""

    changed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    stale: tuple[str, ...] = ()
    root_changed: bool = False
    old_root_hash: str = ""
    new_root_hash: str = ""
