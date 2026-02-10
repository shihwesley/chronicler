"""Regeneration of stale documentation using a pluggable drafter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from chronicler_core.freshness.checker import check_staleness, _load_or_build_tree, _tree_path
from chronicler_core.merkle.tree import compute_file_hash

logger = logging.getLogger(__name__)


class Drafter(Protocol):
    """Protocol for anything that can regenerate a single doc."""

    def draft_single(self, source_path: str) -> bool:
        """Draft docs for a single source file. Returns True on success."""
        ...


class RegenerationReport(BaseModel):
    """Outcome of a regeneration pass."""

    regenerated: list[str] = Field(default_factory=list)
    failed: list[tuple[str, str]] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)


def regenerate_stale(
    project_path: str | Path,
    drafter: Any | None = None,
) -> RegenerationReport:
    """Find stale files and regenerate their docs if a drafter is available.

    Without a drafter, all stale files are returned as skipped. With one,
    each stale file is passed to drafter.draft_single() and the merkle
    tree is updated on success.
    """
    project_path = Path(project_path).resolve()
    report = check_staleness(project_path)

    result = RegenerationReport()

    if not report.stale:
        return result

    # No drafter — everything is skipped
    if drafter is None:
        result.skipped = [entry.source_path for entry in report.stale]
        return result

    # Attempt regeneration for each stale file
    tree = _load_or_build_tree(project_path)
    any_updated = False

    for entry in report.stale:
        try:
            ok = drafter.draft_single(entry.source_path)
        except Exception as exc:
            result.failed.append((entry.source_path, str(exc)))
            continue

        if not ok:
            result.failed.append((entry.source_path, "drafter returned False"))
            continue

        # Update the merkle node with fresh hashes
        source_file = project_path / entry.source_path
        if source_file.is_file():
            new_source_hash = compute_file_hash(source_file)

            # Try to compute the new doc hash if a doc_path exists
            new_doc_hash = None
            node = tree.nodes.get(entry.source_path)
            if node and node.doc_path:
                doc_file = project_path / node.doc_path
                if doc_file.is_file():
                    new_doc_hash = compute_file_hash(doc_file)

            tree.update_node(
                entry.source_path,
                source_hash=new_source_hash,
                doc_hash=new_doc_hash,
            )
            any_updated = True

        result.regenerated.append(entry.source_path)

    # Persist updated tree
    if any_updated:
        tree_file = _tree_path(project_path)
        tree_file.parent.mkdir(parents=True, exist_ok=True)
        tree.save(tree_file)

    return result
