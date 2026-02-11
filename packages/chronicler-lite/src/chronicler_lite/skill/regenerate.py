"""Force-regenerate stale documentation."""

from __future__ import annotations

import sys
from pathlib import Path

from chronicler_core.freshness import regenerate_stale, check_staleness


def main(file_path: str | None = None) -> None:
    root = Path(".").resolve()

    if file_path:
        # Single-file mode: just report staleness for this file
        report = check_staleness(root)
        target = file_path
        match = [e for e in report.stale if e.source_path == target]
        if not match:
            print(f"File is fresh (not stale): {target}")
            return
        print(f"Stale: {target}")
        print(f"  Recorded hash: {match[0].recorded_hash}")
        print(f"  Current hash:  {match[0].current_hash}")
        print(f"  Doc path:      {match[0].doc_path or '(none)'}")
        print(f"\nTo regenerate with LLM, configure a drafter in chronicler.yaml first.")
        return

    # All-stale mode
    result = regenerate_stale(root, drafter=None)

    if not result.skipped and not result.regenerated and not result.failed:
        print("All documentation is fresh. Nothing to regenerate.")
        return

    if result.regenerated:
        print(f"Regenerated ({len(result.regenerated)}):")
        for path in result.regenerated:
            print(f"  {path}")

    if result.skipped:
        print(f"\nStale but skipped ({len(result.skipped)}) — no drafter configured:")
        for path in result.skipped:
            print(f"  {path}")
        print(f"\nConfigure an LLM provider in chronicler.yaml to enable auto-regeneration.")

    if result.failed:
        print(f"\nFailed ({len(result.failed)}):")
        for path, reason in result.failed:
            print(f"  {path}: {reason}")

    # Rebuild INDEX.md if any files were regenerated
    if result.regenerated:
        try:
            from chronicler_lite.skill.index import build_index

            build_index(root)
        except Exception:
            # Non-critical — don't fail the regeneration over an index rebuild error
            pass


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
