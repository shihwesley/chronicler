"""Differ and drift detection for Merkle trees."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from chronicler_core.merkle.models import MerkleDiff, MerkleNode
from chronicler_core.merkle.tree import compute_file_hash

if TYPE_CHECKING:
    from chronicler_core.merkle.tree import MerkleTree


class MerkleTreeDiffer:
    """Compares two Merkle trees and detects on-disk drift."""

    @staticmethod
    def diff(old: MerkleTree, new: MerkleTree) -> MerkleDiff:
        """Compare *old* against *new* and return a diff summary."""
        old_files = {
            p for p, n in old.nodes.items() if n.source_hash is not None
        }
        new_files = {
            p for p, n in new.nodes.items() if n.source_hash is not None
        }

        added = sorted(new_files - old_files)
        removed = sorted(old_files - new_files)
        changed: list[str] = []
        stale_list: list[str] = []

        for p in sorted(old_files & new_files):
            old_node = old.nodes[p]
            new_node = new.nodes[p]
            if old_node.source_hash != new_node.source_hash:
                changed.append(p)
                # Stale = source changed but doc stayed the same
                if old_node.doc_hash == new_node.doc_hash:
                    stale_list.append(p)

        return MerkleDiff(
            changed=tuple(changed),
            added=tuple(added),
            removed=tuple(removed),
            stale=tuple(stale_list),
            root_changed=old.root_hash != new.root_hash,
            old_root_hash=old.root_hash,
            new_root_hash=new.root_hash,
        )

    @staticmethod
    def check_drift(tree: MerkleTree) -> list[MerkleNode]:
        """Re-hash source files on disk; return nodes whose source changed."""
        root = Path(tree.root_path)
        stale: list[MerkleNode] = []
        for path, node in list(tree.nodes.items()):
            if node.source_hash is None:
                continue  # directory node
            fpath = root / node.path
            if not fpath.is_file():
                continue
            current = compute_file_hash(fpath)
            if current != node.source_hash:
                updated = replace(node, stale=True)
                tree.nodes[path] = updated
                stale.append(updated)
        return stale
