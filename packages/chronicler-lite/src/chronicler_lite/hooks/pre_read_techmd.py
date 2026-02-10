"""PreToolUse hook — warns when reading a .tech.md backed by stale source.

Only activates for .tech.md files. Checks the merkle tree to see if
the source file that generated this doc has changed since last scan.
If stale, prints a warning so the developer knows the doc may be outdated.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("chronicler.hooks")


def main(tool_input_file: str) -> None:
    try:
        input_path = Path(tool_input_file)
        if not input_path.is_file():
            return

        try:
            data = json.loads(input_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("chronicler hook: skipping — %s", e)
            return
        file_path = data.get("file_path", "")

        # Only care about .tech.md files
        if not file_path.endswith(".tech.md"):
            return

        target = Path(file_path).resolve()

        # Find project root (walk up looking for chronicler.yaml)
        project_root = _find_project_root(target)
        if project_root is None:
            return

        # Check staleness via the merkle tree
        tree_file = project_root / ".chronicler" / "merkle-tree.json"
        if not tree_file.is_file():
            return

        from chronicler_core.merkle.tree import MerkleTree, compute_file_hash

        tree = MerkleTree.load(tree_file)
        tree.root_path = str(project_root)

        # Find the merkle node whose doc_path matches this .tech.md
        rel_doc = str(target.relative_to(project_root))
        source_node = None
        for node in tree.nodes.values():
            if node.doc_path == rel_doc:
                source_node = node
                break

        if source_node is None or source_node.source_hash is None:
            return

        source_file = project_root / source_node.path
        if not source_file.is_file():
            return

        current_hash = compute_file_hash(source_file)
        if current_hash != source_node.source_hash:
            print(
                f"Chronicler: WARNING — {rel_doc} is stale. "
                f"Source file {source_node.path} has changed since last doc generation. "
                f"Run /chronicler regenerate to update."
            )
    except Exception as e:
        logger.warning("chronicler pre_read_techmd hook failed: %s", e)
        sys.exit(0)


def _find_project_root(start: Path) -> Path | None:
    """Walk up from start looking for chronicler.yaml."""
    search = start.parent if start.is_file() else start
    for _ in range(20):
        if (search / "chronicler.yaml").is_file():
            return search
        parent = search.parent
        if parent == search:
            break
        search = parent
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
