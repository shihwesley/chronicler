"""File tree formatting for LLM context."""

from __future__ import annotations

import re

from chronicler_core.vcs.models import FileNode

# Priority tiers for file tree ordering (lower = higher priority).
_PRIORITY_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"(^|/)package\.json$"), 0),
    (re.compile(r"(^|/)pyproject\.toml$"), 0),
    (re.compile(r"(^|/)Cargo\.toml$"), 0),
    (re.compile(r"(^|/)go\.mod$"), 0),
    (re.compile(r"(^|/)Dockerfile"), 1),
    (re.compile(r"(^|/)\.github/workflows/"), 1),
    (re.compile(r"(^|/)\.gitlab-ci"), 1),
    (re.compile(r"(^|/)(src|lib|app)/"), 2),
]

_MAX_TREE_FILES = 50


def _file_priority(path: str) -> tuple[int, str]:
    """Return (priority_tier, path) for sorting. Lower tier = more important."""
    for pattern, tier in _PRIORITY_PATTERNS:
        if pattern.search(path):
            return (tier, path)
    return (9, path)


class FileTreeFormatter:
    """Renders a list of FileNodes as an indented text tree."""

    def format(self, tree: list[FileNode]) -> str:
        """Format FileNode list as indented text tree, capped at _MAX_TREE_FILES."""
        files = [n for n in tree if n.type == "file"]
        files.sort(key=lambda n: _file_priority(n.path))
        files = files[:_MAX_TREE_FILES]

        # Collect directories that contain selected files.
        dirs_with_files: set[str] = set()
        for f in files:
            parts = f.path.split("/")
            for i in range(1, len(parts)):
                dirs_with_files.add("/".join(parts[:i]))

        # Build ordered lines: insert directory entries before their children.
        seen_dirs: set[str] = set()
        lines: list[str] = []

        # Sort selected files alphabetically for the final output.
        files.sort(key=lambda n: n.path)

        for f in files:
            parts = f.path.split("/")
            # Ensure parent dirs are emitted first.
            for i in range(1, len(parts)):
                d = "/".join(parts[:i])
                if d not in seen_dirs:
                    seen_dirs.add(d)
                    depth = i - 1
                    lines.append("  " * depth + parts[i - 1] + "/")
            # Emit the file itself.
            depth = len(parts) - 1
            lines.append("  " * depth + parts[-1])

        return "\n".join(lines)
