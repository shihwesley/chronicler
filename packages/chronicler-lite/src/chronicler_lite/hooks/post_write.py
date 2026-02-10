"""PostToolUse hook — records file writes as stale candidates.

Reads the TOOL_INPUT_FILE JSON to extract the written file path,
then appends it to .chronicler/.stale-candidates for later batch
staleness checking.

Target: <100ms — no heavy imports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(tool_input_file: str) -> None:
    input_path = Path(tool_input_file)
    if not input_path.is_file():
        return

    try:
        data = json.loads(input_path.read_text())
    except (json.JSONDecodeError, OSError):
        return
    file_path = data.get("file_path")
    if not file_path:
        return

    # Don't track changes to chronicler's own doc output
    if "/.chronicler/" in file_path or file_path.startswith(".chronicler/"):
        return

    # Resolve and validate path BEFORE any filesystem operations
    written_path = Path(file_path).resolve()

    # Find project root by walking up from the written file
    candidates_file = _find_candidates_file(written_path)
    if candidates_file is None:
        return

    # Guard: ensure the written file is under the project root (moved earlier)
    project_root = candidates_file.parent.parent  # .chronicler's parent
    if not written_path.is_relative_to(project_root):
        return  # path outside project, ignore

    candidates_file.parent.mkdir(parents=True, exist_ok=True)
    with open(candidates_file, "a") as f:
        f.write(file_path + "\n")


def _find_candidates_file(written: Path) -> Path | None:
    """Walk up from the written file looking for a .chronicler/ directory."""
    search = written.resolve().parent
    for _ in range(20):  # cap depth to avoid infinite loop
        chronicler_dir = search / ".chronicler"
        if chronicler_dir.is_dir():
            return chronicler_dir / ".stale-candidates"
        parent = search.parent
        if parent == search:
            break
        search = parent
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
