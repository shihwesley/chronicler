"""Builder for constructing Merkle trees from a directory on disk."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from chronicler_core.merkle.models import MerkleNode
from chronicler_core.merkle.tree import (
    DEFAULT_IGNORE,
    MerkleTree,
    _find_doc_for_source,
    _matches_any,
    compute_file_hash,
    compute_hash,
    compute_merkle_hash,
)


class MerkleTreeBuilder:
    """Builds a MerkleTree by walking a source directory on disk."""

    @staticmethod
    def build(
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
            # all ancestor directories are linked so intermediate dirs get nodes.
            parent = str(fpath.parent.relative_to(root_path))
            if parent == ".":
                parent = ""
            children_map[parent].append(rel)

            # Walk up the ancestor chain
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

        # Build directory nodes bottom-up (deepest paths first)
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
                children=tuple(sorted(child_paths)),
            )

        root_hash = nodes[""].hash if "" in nodes else compute_hash(b"")

        return MerkleTree(
            root_hash=root_hash,
            nodes=nodes,
            last_scan=datetime.now(timezone.utc),
            root_path=str(root_path),
        )
