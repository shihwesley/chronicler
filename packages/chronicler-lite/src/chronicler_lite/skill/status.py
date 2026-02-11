"""Staleness report: show freshness status of project documentation."""

from __future__ import annotations

import sys
from pathlib import Path

from chronicler_core.freshness import check_staleness


def main(project_path: str | None = None) -> None:
    root = Path(project_path or ".").resolve()

    try:
        report = check_staleness(root)
    except FileNotFoundError:
        print(f"Error: directory not found: {root}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {root}", file=sys.stderr)
        sys.exit(1)

    fresh_count = report.total_files - len(report.stale) - len(report.uncovered)

    print(f"Chronicler Status: {root.name}\n")
    print(f"  {'Category':<14} {'Count':>6}")
    print(f"  {'-' * 14} {'-' * 6}")
    print(f"  {'Fresh':<14} {fresh_count:>6}")
    print(f"  {'Stale':<14} {len(report.stale):>6}")
    print(f"  {'Uncovered':<14} {len(report.uncovered):>6}")
    print(f"  {'Orphaned':<14} {len(report.orphaned):>6}")
    print(f"  {'-' * 14} {'-' * 6}")
    print(f"  {'Total files':<14} {report.total_files:>6}")
    print(f"  {'Total docs':<14} {report.total_docs:>6}")

    if report.stale:
        print(f"\nStale files:")
        for entry in report.stale:
            doc_label = entry.doc_path or "(no doc)"
            print(f"  {entry.source_path}  ->  {doc_label}")

    if report.orphaned:
        print(f"\nOrphaned docs (no matching source):")
        for path in report.orphaned:
            print(f"  {path}")


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
