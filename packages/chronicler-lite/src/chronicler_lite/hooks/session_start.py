"""SessionStart hook — fast staleness summary for Claude Code startup.

Prints a one-line summary of documentation freshness so the developer
knows immediately if any docs need attention.

Target: <200ms for typical projects.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("chronicler.hooks")


def main(project_path: str | None = None) -> None:
    try:
        import os
        from pathlib import Path

        project = Path(project_path or os.getcwd()).resolve()

        # Quick bail if no chronicler setup in this project
        if not (project / ".chronicler").is_dir():
            return

        from chronicler_core.freshness import check_staleness

        report = check_staleness(project)

        n_stale = len(report.stale)
        n_uncovered = len(report.uncovered)
        n_orphaned = len(report.orphaned)

        if n_stale or n_uncovered or n_orphaned:
            parts = []
            if n_stale:
                parts.append(f"{n_stale} stale")
            if n_uncovered:
                parts.append(f"{n_uncovered} uncovered")
            if n_orphaned:
                parts.append(f"{n_orphaned} orphaned docs")
            print(f"Chronicler: {', '.join(parts)}")
        else:
            print(f"Chronicler: all docs fresh ({report.total_docs} tracked)")
    except Exception as e:
        logger.warning("chronicler session_start hook failed: %s", e)
        sys.exit(0)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    main(path)
