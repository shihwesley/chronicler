"""YAML frontmatter generator for .tech.md files."""

from __future__ import annotations

import re
from collections import Counter

from chronicler.vcs.models import FileNode, RepoMetadata

# Directory patterns that indicate architectural layer.
_LAYER_PATTERNS: dict[str, list[str]] = {
    "api": ["api", "routes", "controllers", "endpoints"],
    "logic": ["services", "core", "lib", "utils"],
    "infrastructure": ["infra", "terraform", "deploy", "k8s", "helm"],
}

# Keys under which CODEOWNERS content might appear in key_files.
_CODEOWNERS_PATHS = ("CODEOWNERS", ".github/CODEOWNERS")


def generate_frontmatter(
    metadata: RepoMetadata,
    key_files: dict[str, str],
    tree: list[FileNode],
) -> dict:
    """Generate YAML frontmatter dict from repo metadata.

    Returns a dict ready for yaml.dump() with required .tech.md fields.
    """
    return {
        "component_id": metadata.full_name,
        "version": "0.1.0",
        "owner_team": _parse_owner(key_files),
        "layer": _infer_layer(tree),
        "security_level": "low",
        "governance": {
            "business_impact": None,
            "verification_status": "ai_draft",
            "visibility": "internal",
        },
        "edges": [],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_layer(tree: list[FileNode]) -> str:
    """Infer architectural layer from directory names in the tree."""
    dir_names = {node.name for node in tree if node.type == "dir"}

    counts: Counter[str] = Counter()
    for layer, patterns in _LAYER_PATTERNS.items():
        for pat in patterns:
            if pat in dir_names:
                counts[layer] += 1

    if not counts:
        return "logic"
    return counts.most_common(1)[0][0]


def _parse_owner(key_files: dict[str, str]) -> str:
    """Extract team name from CODEOWNERS global owner line."""
    content: str | None = None
    for path in _CODEOWNERS_PATHS:
        if path in key_files:
            content = key_files[path]
            break

    if content is None:
        return "unknown"

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("*"):
            # e.g. "* @org/platform-team" or "* @org/platform-team @org/other"
            match = re.search(r"@[\w-]+/([\w-]+)", line)
            if match:
                return match.group(1)
    return "unknown"
