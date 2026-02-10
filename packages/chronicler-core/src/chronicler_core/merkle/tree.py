"""Merkle tree implementation for tracking source/doc drift."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
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

        Files matching *ignore_patterns* (and the built-in defaults) are
        skipped. For each source file we also search for a paired
        ``.tech.md`` inside *doc_dir*.
        """
        root_path = root_path.resolve()
        ignore = set(DEFAULT_IGNORE)
        if ignore_patterns:
            ignore.update(ignore_patterns)

        nodes: dict[str, MerkleNode] = {}
        # dir_path -> list of child relative paths
        children_map: dict[str, list[str]] = defaultdict(list)

        # Collect all source files
        all_files: list[Path] = []
        for p in sorted(root_path.rglob("*")):
            if _matches_any(p.relative_to(root_path), ignore):
                continue
            if p.is_file():
                all_files.append(p)

        for fpath in all_files:
            rel = str(fpath.relative_to(root_path))
            source_hash = compute_file_hash(fpath)

            # Look for a paired doc
            doc_path_obj = _find_doc_for_source(rel, doc_dir, root_path)
            doc_hash: str | None = None
            doc_path: str | None = None
            if doc_path_obj is not None:
                doc_hash = compute_file_hash(doc_path_obj)
                doc_path = str(doc_path_obj.relative_to(root_path))

            node = MerkleNode(
                path=rel,
                hash=source_hash,
                source_hash=source_hash,
                doc_hash=doc_hash,
                doc_path=doc_path,
            )
            nodes[rel] = node

            # Register file as direct child of its parent, and ensure
            # all ancestor directories are linked to each other so that
            # intermediate dirs (e.g. a/b with only subdirs) get nodes.
            parent = str(fpath.parent.relative_to(root_path))
            if parent == ".":
                parent = ""
            children_map[parent].append(rel)

            # Walk up the ancestor chain, registering each dir as a
            # child of its own parent (duplicates are fine, we dedupe later).
            cur = parent
            while cur:
                if "/" in cur:
                    ancestor = cur.rsplit("/", 1)[0]
                else:
                    ancestor = ""
                children_map[ancestor].append(cur)
                cur = ancestor if ancestor != cur else ""
                if not cur:
                    break

        # Deduplicate children lists
        for key in children_map:
            children_map[key] = list(dict.fromkeys(children_map[key]))

        # Build directory nodes bottom-up (deepest paths first).
        # Use len(parts) so that "src" (depth 1) sorts before "" (depth 0).
        def _depth(d: str) -> int:
            return len(d.split("/")) if d else 0

        dir_keys = sorted(children_map.keys(), key=_depth, reverse=True)
        for dpath in dir_keys:
            child_paths = children_map[dpath]
            child_hashes = [nodes[c].hash for c in sorted(child_paths)]
            dir_hash = compute_merkle_hash(child_hashes)
            nodes[dpath] = MerkleNode(
                path=dpath,
                hash=dir_hash,
                children=sorted(child_paths),
            )

        root_hash = nodes[""].hash if "" in nodes else compute_hash(b"")

        return cls(
            root_hash=root_hash,
            nodes=nodes,
            last_scan=datetime.now(timezone.utc),
            root_path=str(root_path),
        )

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def check_drift(self) -> list[MerkleNode]:
        """Re-hash source files on disk; return nodes whose source changed."""
        root = Path(self.root_path)
        stale: list[MerkleNode] = []
        for node in self.nodes.values():
            if node.source_hash is None:
                continue  # directory node
            fpath = root / node.path
            if not fpath.is_file():
                continue
            current = compute_file_hash(fpath)
            if current != node.source_hash:
                node.stale = True
                stale.append(node)
        return stale

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(self, other: MerkleTree) -> MerkleDiff:
        """Compare *self* (old) against *other* (new)."""
        old_files = {
            p for p, n in self.nodes.items() if n.source_hash is not None
        }
        new_files = {
            p for p, n in other.nodes.items() if n.source_hash is not None
        }

        added = sorted(new_files - old_files)
        removed = sorted(old_files - new_files)
        changed: list[str] = []
        stale_list: list[str] = []

        for p in sorted(old_files & new_files):
            old_node = self.nodes[p]
            new_node = other.nodes[p]
            if old_node.source_hash != new_node.source_hash:
                changed.append(p)
                # Stale = source changed but doc stayed the same
                if old_node.doc_hash == new_node.doc_hash:
                    stale_list.append(p)

        return MerkleDiff(
            changed=changed,
            added=added,
            removed=removed,
            stale=stale_list,
            root_changed=self.root_hash != other.root_hash,
            old_root_hash=self.root_hash,
            new_root_hash=other.root_hash,
        )

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
        node.source_hash = source_hash
        node.hash = source_hash
        if doc_hash is not None:
            node.doc_hash = doc_hash
        node.stale = False

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
                    "children": n.children,
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
                children=ndata.get("children", []),
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
