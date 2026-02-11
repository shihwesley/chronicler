"""Generate thin _map.md files from .tech.md frontmatter edges.

Produces a per-project map with [[wikilinks]] so Obsidian's graph view
can draw connections between components without duplicating .tech.md content.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def parse_tech_md_edges(tech_md_path: Path) -> list[dict]:
    """Parse YAML frontmatter from a .tech.md file and return its edges list.

    Each edge is expected to have at least a 'target' key, and optionally 'type'.
    """
    if not tech_md_path.is_file():
        return []
    content = tech_md_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return []
    end = content.find("---", 3)
    if end == -1:
        return []
    try:
        fm = yaml.safe_load(content[3:end])
    except yaml.YAMLError:
        return []
    if not isinstance(fm, dict):
        return []
    edges = fm.get("edges", [])
    if not isinstance(edges, list):
        return []
    return edges


def parse_component_id(tech_md_path: Path) -> str:
    """Extract component_id from frontmatter, falling back to filename stem."""
    content = tech_md_path.read_text(encoding="utf-8")
    component_id = tech_md_path.stem.replace(".tech", "")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(content[3:end])
                if isinstance(fm, dict) and "component_id" in fm:
                    component_id = fm["component_id"]
            except yaml.YAMLError:
                pass
    return component_id


def build_edge_graph(chronicler_dir: Path) -> dict[str, list[dict]]:
    """Scan all .tech.md files and build component_id -> edges adjacency map."""
    graph: dict[str, list[dict]] = {}
    if not chronicler_dir.is_dir():
        return graph
    for md in sorted(chronicler_dir.glob("*.tech.md")):
        edges = parse_tech_md_edges(md)
        component_id = parse_component_id(md)
        graph[component_id] = edges
    return graph


class MapGenerator:
    """Generates a _map.md from .tech.md frontmatter edges."""

    def __init__(self, chronicler_dir: Path) -> None:
        self.chronicler_dir = chronicler_dir

    def _derive_project_name(self) -> str:
        """Get the project name from the parent directory."""
        parent = self.chronicler_dir.parent
        if parent == self.chronicler_dir:
            return "Root"
        return parent.name or "Root"

    def generate(self) -> str:
        """Build _map.md content from .tech.md edges."""
        graph = build_edge_graph(self.chronicler_dir)
        project_name = self._derive_project_name()

        lines = [
            "---",
            f'title: "{project_name} Component Map"',
            "tags: [chronicler-map]",
            "cssclass: chronicler-map",
            "---",
            "",
        ]

        if not graph:
            lines.append("No components found.")
            return "\n".join(lines) + "\n"

        for component_id, edges in graph.items():
            lines.append(f"## {component_id}")

            if not edges:
                lines.append("- (no edges)")
            else:
                for edge in edges:
                    target = edge.get("target", "unknown")
                    edge_type = edge.get("type", "")
                    suffix = f" ({edge_type})" if edge_type else ""
                    lines.append(f"- [[{target}]]{suffix}")

            lines.append("")

        return "\n".join(lines)

    def write(self) -> Path:
        """Write _map.md to the .chronicler/ directory. Returns the path."""
        content = self.generate()
        out = self.chronicler_dir / "_map.md"
        out.write_text(content, encoding="utf-8")
        return out
