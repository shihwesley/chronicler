"""Data models for the Merkle tree subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MerkleNode:
    """A node in the Merkle tree, representing either a file or directory."""

    path: str
    hash: str
    children: list[str] = field(default_factory=list)
    source_hash: str | None = None
    doc_hash: str | None = None
    doc_path: str | None = None
    stale: bool = False


@dataclass
class MerkleDiff:
    """Result of comparing two Merkle trees."""

    changed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    root_changed: bool = False
    old_root_hash: str = ""
    new_root_hash: str = ""
