"""Project initialization: detect type, generate config, build merkle tree, install hooks."""

from __future__ import annotations

import json
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

# Hook definitions to install into .claude/settings.json
CHRONICLER_HOOKS = {
    "SessionStart": [
        {"command": "~/.claude/hooks/chronicler/session-start.sh"}
    ],
    "PostToolUse": [
        {"matcher": "Write|Edit", "command": "~/.claude/hooks/chronicler/post-write.sh"}
    ],
    "PreToolUse": [
        {"matcher": "Read", "command": "~/.claude/hooks/chronicler/pre-read-techmd.sh"}
    ],
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


def _deploy_hook_scripts() -> None:
    """Copy bundled shell scripts to ~/.claude/hooks/chronicler/."""
    scripts_dir = Path(__file__).resolve().parent.parent / "hooks" / "scripts"
    target_dir = Path.home() / ".claude" / "hooks" / "chronicler"
    target_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    import stat

    for script in scripts_dir.glob("*.sh"):
        dest = target_dir / script.name
        shutil.copy2(script, dest)
        dest.chmod(dest.stat().st_mode | stat.S_IEXEC)


def install_hooks(project_path: Path) -> None:
    """Deploy hook scripts and merge chronicler hooks into .claude/settings.json."""
    # Copy shell scripts to ~/.claude/hooks/chronicler/
    _deploy_hook_scripts()

    settings_path = project_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})

    for event, new_entries in CHRONICLER_HOOKS.items():
        existing = hooks.get(event, [])
        # Avoid duplicates by checking command strings (handle both dict and string entries)
        existing_cmds: set[str] = set()
        for e in existing:
            if isinstance(e, dict) and e.get("command"):
                existing_cmds.add(e["command"])
            elif isinstance(e, str):
                existing_cmds.add(e)
        for entry in new_entries:
            if entry["command"] not in existing_cmds:
                existing.append(entry)
        hooks[event] = existing

    settings["hooks"] = hooks
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"  Hooks installed in .claude/settings.json")


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

        # 4. Install hooks
        install_hooks(root)

        print(f"\nDone. Run `/chronicler status` to check freshness.")
    except FileNotFoundError:
        print(f"Error: directory not found: {root}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {root}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
