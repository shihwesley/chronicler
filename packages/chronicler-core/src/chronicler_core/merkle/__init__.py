"""Merkle tree subsystem for source/doc drift tracking."""

from chronicler_core.merkle.models import MerkleDiff, MerkleNode
from chronicler_core.merkle.scanner import DiffResult, MercatorScanner, ScanResult
from chronicler_core.merkle.tree import (
    MerkleTree,
    compute_hash,
    compute_file_hash,
    compute_merkle_hash,
)


def build_tree(*args, **kwargs):
    """Convenience wrapper around MerkleTree.build()."""
    return MerkleTree.build(*args, **kwargs)


def check_drift(tree: MerkleTree) -> list[MerkleNode]:
    """Convenience wrapper around MerkleTree.check_drift()."""
    return tree.check_drift()


__all__ = [
    "DiffResult",
    "MercatorScanner",
    "MerkleDiff",
    "MerkleNode",
    "MerkleTree",
    "ScanResult",
    "build_tree",
    "check_drift",
    "compute_file_hash",
    "compute_hash",
    "compute_merkle_hash",
]
