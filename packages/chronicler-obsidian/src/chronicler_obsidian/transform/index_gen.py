"""Generates MOC (Map of Content) index notes for vault navigation."""

from .pipeline import Transform


class IndexGenerator(Transform):
    def __init__(self):
        self.components: dict[str, list[dict]] = {}

    def apply(self, content: str, metadata: dict) -> str:
        # Collect metadata per layer, don't modify content
        layer = metadata.get("layer", "unknown")
        comp_id = metadata.get("component_id", "unknown")
        if layer not in self.components:
            self.components[layer] = []
        self.components[layer].append({
            "component_id": comp_id,
            "version": metadata.get("version", ""),
            "owner_team": metadata.get("owner_team", ""),
        })
        return content

    def generate(self) -> str:
        """Generate _index.md content with Dataview queries."""
        parts: list[str] = []

        # Frontmatter
        parts.append("---")
        parts.append('title: "Chronicler Documentation Index"')
        parts.append("tags: [chronicler-index]")
        parts.append("---")
        parts.append("")
        parts.append("# Project Documentation")
        parts.append("")

        # Grouped by layer
        parts.append("## By Layer")
        for layer in sorted(self.components):
            parts.append(f"### {layer.title()}")
            for comp in sorted(self.components[layer], key=lambda c: c["component_id"]):
                parts.append(f"- [[{comp['component_id']}]]")
            parts.append("")

        # Dataview: All Services
        parts.append("## Dataview: All Services")
        parts.append("")
        parts.append("```dataview")
        parts.append("TABLE version, owner_team, security_level")
        parts.append("FROM #tech-doc")
        parts.append("SORT layer, component_id")
        parts.append("```")
        parts.append("")

        # Dataview: Dependency Graph
        parts.append("## Dataview: Dependency Graph")
        parts.append("")
        parts.append("```dataview")
        parts.append('TABLE dependencies AS "Depends On", called_by AS "Called By"')
        parts.append("FROM #tech-doc")
        parts.append("WHERE length(dependencies) > 0")
        parts.append("SORT component_id")
        parts.append("```")
        parts.append("")

        return "\n".join(parts)
