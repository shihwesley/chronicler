"""Staleness detection for source/doc pairs via the merkle tree."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from chronicler_core.merkle.tree import MerkleTree, compute_file_hash

logger = logging.getLogger(__name__)


class StaleEntry(BaseModel):
    """A single source file whose content has drifted from the merkle record."""

    source_path: str
    doc_path: str | None = None
    current_hash: str
    recorded_hash: str


class StalenessReport(BaseModel):
    """Full freshness status for a project."""

    stale: list[StaleEntry] = Field(default_factory=list)
    uncovered: list[str] = Field(default_factory=list)
    orphaned: list[str] = Field(default_factory=list)
    total_files: int = 0
    total_docs: int = 0


def _tree_path(project_path: Path) -> Path:
    """Where the merkle tree JSON lives inside .chronicler/."""
    return project_path / ".chronicler" / "merkle-tree.json"


def _load_or_build_tree(project_path: Path) -> MerkleTree:
    """Load a saved merkle tree, or build one from scratch."""
    tree_file = _tree_path(project_path)
    if tree_file.is_file():
        tree = MerkleTree.load(tree_file)
        # Patch root_path so drift checks resolve against the right directory
        tree.root_path = str(project_path.resolve())
        return tree
    return MerkleTree.build(project_path.resolve())


def _collect_tech_md_files(project_path: Path, doc_dir: str = ".chronicler") -> set[str]:
    """Walk the doc directory and return relative paths of all .tech.md files."""
    doc_root = project_path / doc_dir
    if not doc_root.is_dir():
        return set()
    result: set[str] = set()
    for p in doc_root.rglob("*.tech.md"):
        result.add(str(p.relative_to(project_path)))
    return result


def check_staleness(project_path: str | Path) -> StalenessReport:
    """Analyze a project and report stale, uncovered, and orphaned files.

    1. Loads (or builds) the merkle tree for the project.
    2. Rehashes source files on disk to find drift (stale entries).
    3. Identifies source files with no paired .tech.md (uncovered).
    4. Identifies .tech.md files not referenced by any source (orphaned).
    """
    project_path = Path(project_path).resolve()
    tree = _load_or_build_tree(project_path)

    # --- Stale detection ---
    stale_entries: list[StaleEntry] = []
    file_nodes = [
        node for node in tree.nodes.values()
        if node.source_hash is not None  # skip directory nodes
    ]

    for node in file_nodes:
        fpath = project_path / node.path
        if not fpath.is_file():
            continue
        current = compute_file_hash(fpath)
        if current != node.source_hash:
            stale_entries.append(StaleEntry(
                source_path=node.path,
                doc_path=node.doc_path,
                current_hash=current,
                recorded_hash=node.source_hash,
            ))

    # --- Uncovered detection ---
    # Source files whose merkle node has no doc_path
    uncovered = sorted(
        node.path for node in file_nodes
        if node.doc_path is None and (project_path / node.path).is_file()
    )

    # --- Orphaned detection ---
    # .tech.md files on disk not referenced by any merkle node
    referenced_docs = {
        node.doc_path for node in file_nodes
        if node.doc_path is not None
    }
    all_tech_md = _collect_tech_md_files(project_path)
    orphaned = sorted(all_tech_md - referenced_docs)

    # --- Counts ---
    total_files = sum(1 for n in file_nodes if (project_path / n.path).is_file())
    total_docs = len(referenced_docs & all_tech_md)

    return StalenessReport(
        stale=stale_entries,
        uncovered=uncovered,
        orphaned=orphaned,
        total_files=total_files,
        total_docs=total_docs,
    )
