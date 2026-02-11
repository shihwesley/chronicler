"""Merkle tree implementation for tracking source/doc drift."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from chronicler_core.merkle.models import MerkleDiff, MerkleNode

# Directories always skipped during tree build
DEFAULT_IGNORE = {
    ".git",
    "node_modules",
    "build",
    "dist",
    "__pycache__",
    ".venv",
    ".worktrees",
    ".tox",
}


def compute_hash(content: bytes) -> str:
    """SHA-256 hash, truncated to the first 12 hex characters."""
    return hashlib.sha256(content).hexdigest()[:12]


def compute_file_hash(path: Path) -> str:
    """Read a file from disk and return its truncated SHA-256 hash."""
    return compute_hash(path.read_bytes())


def compute_merkle_hash(child_hashes: list[str]) -> str:
    """Compute a parent hash from sorted child hashes.

    Sorts the hashes lexicographically, joins them, then hashes the result.
    """
    joined = "".join(sorted(child_hashes))
    return compute_hash(joined.encode())


def _matches_any(path: Path, patterns: set[str]) -> bool:
    """Check whether any component of *path* matches one of *patterns*."""
    return any(part in patterns for part in path.parts)


def _find_doc_for_source(
    source_rel: str, doc_dir: str, root: Path
) -> Path | None:
    """Try to locate a .tech.md paired with a source file.

    Two strategies:
    1. Look for <doc_dir>/<stem>.tech.md next to the source file.
    2. Look for <doc_dir>/<component_id>.tech.md where component_id is
       derived from the relative path (slashes replaced with dashes).
    """
    src = Path(source_rel)
    stem = src.stem

    # Strategy 1: sibling doc directory
    sibling_doc = root / src.parent / doc_dir / f"{stem}.tech.md"
    # Guard against path traversal escaping root
    if sibling_doc.resolve().is_relative_to(root.resolve()) and sibling_doc.is_file():
        return sibling_doc

    # Strategy 2: root doc directory with component_id naming
    component_id = re.sub(r"[/\\]", "-", str(src.with_suffix("")))
    root_doc = root / doc_dir / f"{component_id}.tech.md"
    # Guard against path traversal escaping root
    if root_doc.resolve().is_relative_to(root.resolve()) and root_doc.is_file():
        return root_doc

    return None


class MerkleTree:
    """Merkle tree over a source directory, tracking source/doc hashes."""

    version: int = 1
    algorithm: str = "sha256"

    def __init__(
        self,
        root_hash: str,
        nodes: dict[str, MerkleNode],
        last_scan: datetime,
        root_path: str = "",
    ) -> None:
        self.root_hash = root_hash
        self.nodes = nodes
        self.last_scan = last_scan
        self.root_path = root_path

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        root_path: Path,
        doc_dir: str = ".chronicler",
        ignore_patterns: list[str] | None = None,
    ) -> MerkleTree:
        """Walk *root_path* and construct a full Merkle tree.

        Delegates to :class:`~chronicler_core.merkle.builder.MerkleTreeBuilder`.
        """
        from chronicler_core.merkle.builder import MerkleTreeBuilder

        return MerkleTreeBuilder.build(root_path, doc_dir, ignore_patterns)

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def check_drift(self) -> list[MerkleNode]:
        """Re-hash source files on disk; return nodes whose source changed.

        Delegates to :class:`~chronicler_core.merkle.differ.MerkleTreeDiffer`.
        """
        from chronicler_core.merkle.differ import MerkleTreeDiffer

        return MerkleTreeDiffer.check_drift(self)

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(self, other: MerkleTree) -> MerkleDiff:
        """Compare *self* (old) against *other* (new).

        Delegates to :class:`~chronicler_core.merkle.differ.MerkleTreeDiffer`.
        """
        from chronicler_core.merkle.differ import MerkleTreeDiffer

        return MerkleTreeDiffer.diff(self, other)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def update_node(
        self,
        path: str,
        source_hash: str,
        doc_hash: str | None = None,
    ) -> None:
        """Update a single node's hashes."""
        if path not in self.nodes:
            raise KeyError(f"Node not found: {path}")
        node = self.nodes[path]
        updates: dict = {"source_hash": source_hash, "hash": source_hash, "stale": False}
        if doc_hash is not None:
            updates["doc_hash"] = doc_hash
        self.nodes[path] = replace(node, **updates)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize the tree to a JSON string."""
        data = {
            "version": self.version,
            "algorithm": self.algorithm,
            "root_hash": self.root_hash,
            "root_path": self.root_path,
            "last_scan": self.last_scan.isoformat(),
            "nodes": {
                path: {
                    "path": n.path,
                    "hash": n.hash,
                    "children": list(n.children),
                    "source_hash": n.source_hash,
                    "doc_hash": n.doc_hash,
                    "doc_path": n.doc_path,
                    "stale": n.stale,
                }
                for path, n in self.nodes.items()
            },
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, data: str) -> MerkleTree:
        """Deserialize a tree from a JSON string."""
        obj = json.loads(data)
        nodes: dict[str, MerkleNode] = {}
        for path, ndata in obj["nodes"].items():
            nodes[path] = MerkleNode(
                path=ndata["path"],
                hash=ndata["hash"],
                children=tuple(ndata.get("children", [])),
                source_hash=ndata.get("source_hash"),
                doc_hash=ndata.get("doc_hash"),
                doc_path=ndata.get("doc_path"),
                stale=ndata.get("stale", False),
            )
        return cls(
            root_hash=obj["root_hash"],
            nodes=nodes,
            last_scan=datetime.fromisoformat(obj["last_scan"]),
            root_path=obj.get("root_path", ""),
        )

    def save(self, path: Path) -> None:
        """Write the tree to a JSON file."""
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> MerkleTree:
        """Read a tree from a JSON file."""
        return cls.from_json(path.read_text())
