"""INDEX.md generator — builds a grouped component index from .tech.md frontmatter."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


def parse_tech_md_metadata(path: Path) -> dict | None:
    """Extract component_id, layer, and Purpose text from a single .tech.md file.

    Returns None if the file can't be parsed.
    """
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    try:
        fm = yaml.safe_load(content[3:end])
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None

    component_id = fm.get("component_id", "")
    layer = fm.get("layer", "unknown")

    # Extract Purpose section (first paragraph after "## Purpose")
    purpose = ""
    purpose_match = re.search(r"^## Purpose\s*\n(.+?)(?:\n\n|\n##|\Z)", content, re.MULTILINE | re.DOTALL)
    if purpose_match:
        purpose = purpose_match.group(1).strip()
        # Collapse to single line
        purpose = " ".join(purpose.split("\n"))

    return {
        "component_id": component_id,
        "layer": layer,
        "purpose": purpose,
        "tech_md_filename": path.name,
    }


def group_by_package(entries: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Group entries by package name and subsystem.

    Returns {package_name: {subsystem: [entries]}}.
    Root files (no packages/ prefix) go under "root".
    """
    grouped: dict[str, dict[str, list[dict]]] = {}

    for entry in entries:
        cid = entry["component_id"]
        parts = cid.split("/")

        # Detect package: packages/<name>/src/<pkg_name>/...
        if len(parts) >= 4 and parts[0] == "packages":
            package = parts[1]
            # Find subsystem: everything between the Python package root and the filename
            # e.g. packages/chronicler-core/src/chronicler_core/drafter/drafter.py
            # → package="chronicler-core", subsystem="drafter"
            # Find the src/<pkg>/ prefix end
            src_idx = None
            for i, p in enumerate(parts):
                if p == "src":
                    src_idx = i
                    break
            if src_idx is not None and src_idx + 2 < len(parts):
                # parts after src/<pkg_name>/ but before filename
                sub_parts = parts[src_idx + 2 : -1]
                subsystem = sub_parts[0] if sub_parts else "(root)"
            else:
                subsystem = "(root)"
        else:
            package = "root"
            subsystem = "(root)"

        grouped.setdefault(package, {}).setdefault(subsystem, []).append(entry)

    return grouped


def _short_component_path(component_id: str) -> str:
    """Shorten component_id for display.

    Strips the packages/<name>/src/<pkg_name>/ prefix for readability.
    e.g. packages/chronicler-core/src/chronicler_core/drafter/drafter.py
      → chronicler_core/drafter/drafter.py
    """
    parts = component_id.split("/")
    if len(parts) >= 4 and parts[0] == "packages":
        # Find src/ and skip to the package root after it
        for i, p in enumerate(parts):
            if p == "src" and i + 1 < len(parts):
                return "/".join(parts[i + 1 :])
    return component_id


def _subsystem_display_name(subsystem: str) -> str:
    """Format subsystem name for section headers."""
    if subsystem == "(root)":
        return "Root"
    return subsystem.replace("_", " ").title()


def build_index(project_path: Path) -> Path:
    """Scan .chronicler/*.tech.md, build grouped INDEX.md. Returns the output path."""
    chronicler_dir = project_path / ".chronicler"
    if not chronicler_dir.is_dir():
        chronicler_dir.mkdir(parents=True, exist_ok=True)

    # Collect metadata from all .tech.md files
    entries = []
    for md in sorted(chronicler_dir.glob("*.tech.md")):
        meta = parse_tech_md_metadata(md)
        if meta and meta["component_id"]:
            entries.append(meta)

    grouped = group_by_package(entries)

    # Build markdown
    lines = [
        "# Chronicler Technical Index",
        "",
        "> Read this file first when exploring the codebase. For details on any component, read its `.tech.md` file.",
        "> Naming convention: `path/to/file.py` → `.chronicler/path--to--file.py.tech.md`",
        "",
    ]

    # Package display order: "root" first, then alphabetical
    pkg_order = sorted(grouped.keys(), key=lambda k: ("" if k == "root" else k))

    # Friendly package names
    pkg_labels = {
        "root": f"{project_path.name} (root)",
        "chronicler-core": "chronicler-core",
        "chronicler-lite": "chronicler-lite (Claude Code plugin)",
        "chronicler-enterprise": "chronicler-enterprise",
        "chronicler-obsidian": "chronicler-obsidian",
    }

    for pkg in pkg_order:
        subsystems = grouped[pkg]
        label = pkg_labels.get(pkg, pkg)
        lines.append(f"## {label}")
        lines.append("")

        sub_order = sorted(subsystems.keys(), key=lambda k: ("" if k == "(root)" else k))

        for sub in sub_order:
            sub_entries = subsystems[sub]
            if len(subsystems) > 1 or sub != "(root)":
                lines.append(f"### {_subsystem_display_name(sub)}")
            lines.append("| Component | Layer | Purpose |")
            lines.append("|-----------|-------|---------|")

            for entry in sub_entries:
                short = _short_component_path(entry["component_id"])
                purpose = entry["purpose"]
                # Truncate long purposes for table readability
                if len(purpose) > 120:
                    purpose = purpose[:117] + "..."
                lines.append(f"| `{short}` | {entry['layer']} | {purpose} |")

            lines.append("")

    index_path = chronicler_dir / "INDEX.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  INDEX.md generated: {len(entries)} components indexed")
    return index_path


def main(project_path: str | None = None) -> None:
    root = Path(project_path or ".").resolve()

    try:
        path = build_index(root)
        print(f"\nWrote {path}")
    except FileNotFoundError:
        print(f"Error: directory not found: {root}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {root}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
