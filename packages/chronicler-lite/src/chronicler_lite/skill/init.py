"""Project initialization: detect type, generate config, build merkle tree, update CLAUDE.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from chronicler_core.config.loader import DEFAULT_CONFIG_TEMPLATE
from chronicler_core.merkle import MerkleTree

# Sentinel files that identify project types
PROJECT_MARKERS: dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "Package.swift": "swift",
    "Gemfile": "ruby",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
    "mix.exs": "elixir",
}


def detect_project_type(project_path: Path) -> str | None:
    """Scan for known marker files and return the project type."""
    for marker, lang in PROJECT_MARKERS.items():
        if (project_path / marker).exists():
            return lang
    return None


def generate_config(project_path: Path) -> Path:
    """Write chronicler.yaml from the default template. Returns the path."""
    config_path = project_path / "chronicler.yaml"
    if config_path.exists():
        print(f"  chronicler.yaml already exists, skipping")
        return config_path
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
    print(f"  Created chronicler.yaml")
    return config_path


def build_merkle(project_path: Path) -> MerkleTree:
    """Build and save the merkle tree for drift tracking."""
    tree = MerkleTree.build(project_path.resolve())
    out_dir = project_path / ".chronicler"
    out_dir.mkdir(parents=True, exist_ok=True)
    tree_path = out_dir / "merkle-tree.json"
    tree.save(tree_path)
    node_count = sum(1 for n in tree.nodes.values() if n.source_hash is not None)
    print(f"  Merkle tree built: {node_count} files indexed")
    return tree


EXPLORATION_PROTOCOL = """\

## Exploration Protocol

When exploring or understanding this codebase:

1. **Start with the index.** Read `.chronicler/INDEX.md` for the full component map with one-line purposes.
2. **Dive into .tech.md** for any component you need to understand. Each has purpose, key functions, dependencies, and architectural notes. Path convention: `path/to/file.py` → `.chronicler/path--to--file.py.tech.md`
3. **Read source only when modifying.** The .tech.md gives you enough context for understanding; read the actual source only when you need to edit it or when the .tech.md is flagged stale.
4. **Check edges.** The `edges` field in each .tech.md frontmatter maps imports — use it to trace dependencies without grepping.
"""

# Patterns that indicate an exploration protocol section already exists
_PROTOCOL_MARKERS = re.compile(
    r"^##\s+(Exploration Protocol|Chronicler)\s*$", re.MULTILINE
)


def update_claude_md(project_path: Path) -> None:
    """Inject the exploration protocol into CLAUDE.md.

    - If CLAUDE.md exists and already has the section, skip.
    - If CLAUDE.md exists without it, append.
    - If CLAUDE.md doesn't exist, create a minimal one.
    """
    claude_md = project_path / "CLAUDE.md"

    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        if _PROTOCOL_MARKERS.search(content):
            print(f"  CLAUDE.md already has exploration protocol, skipping")
            return
        # Append to existing
        if not content.endswith("\n"):
            content += "\n"
        content += EXPLORATION_PROTOCOL
        claude_md.write_text(content, encoding="utf-8")
        print(f"  Appended exploration protocol to CLAUDE.md")
    else:
        content = f"# {project_path.name}\n{EXPLORATION_PROTOCOL}"
        claude_md.write_text(content, encoding="utf-8")
        print(f"  Created CLAUDE.md with exploration protocol")


def main(project_path: str | None = None) -> None:
    root = Path(project_path or ".").resolve()

    try:
        print(f"Chronicler init: {root}\n")

        # 1. Detect project type
        lang = detect_project_type(root)
        if lang:
            print(f"  Detected project type: {lang}")
        else:
            print(f"  Could not auto-detect project type (using defaults)")

        # 2. Generate config
        generate_config(root)

        # 3. Build merkle tree
        build_merkle(root)

        # 4. Update CLAUDE.md with exploration protocol
        update_claude_md(root)

        print(f"\nDone. Hooks are managed by the plugin — no manual install needed.")
        print(f"Run `/chronicler:status` to check freshness.")
        print(f"Run `/chronicler:regenerate` to generate .tech.md files.")
    except FileNotFoundError:
        print(f"Error: directory not found: {root}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {root}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
