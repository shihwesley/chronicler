"""Appends Dataview inline fields from .tech.md YAML metadata."""

import re

from .pipeline import Transform

# Edge types that mean "this component depends on target"
_DEPENDS_TYPES = {"reads", "writes", "calls"}
# Edge types that mean "target depends on this component"
_CALLED_BY_TYPES = {"called_by", "consumed_by"}


class DataviewInjector(Transform):
    def apply(self, content: str, metadata: dict) -> str:
        edges = metadata.get("edges", [])
        if not edges:
            return content

        lines = _build_dataview_lines(edges)
        if not lines:
            return content

        block = "\n".join(lines)
        return _inject_dependencies_section(content, block)


def _build_dataview_lines(edges: list[dict]) -> list[str]:
    lines: list[str] = []
    for edge in edges:
        target = edge.get("target", "")
        edge_type = edge.get("type", "")
        via = edge.get("via", "")
        suffix = f" via {via}" if via else ""

        if edge_type in _DEPENDS_TYPES:
            lines.append(f"[depends_on:: [[{target}]]]{suffix}")
        elif edge_type in _CALLED_BY_TYPES:
            lines.append(f"[called_by:: [[{target}]]]{suffix}")
    return lines


def _inject_dependencies_section(content: str, block: str) -> str:
    # If ## Dependencies already exists, inject after the heading
    dep_match = re.search(r"^(## Dependencies\s*)$", content, re.MULTILINE)
    if dep_match:
        insert_pos = dep_match.end()
        return content[:insert_pos] + "\n\n" + block + "\n" + content[insert_pos:]

    # Otherwise insert a new section before the first ## heading
    first_h2 = re.search(r"^## ", content, re.MULTILINE)
    if first_h2:
        pos = first_h2.start()
        section = f"## Dependencies\n\n{block}\n\n"
        return content[:pos] + section + content[pos:]

    # No headings — append at end
    return content.rstrip() + f"\n\n## Dependencies\n\n{block}\n"
