"""Injects YAML frontmatter with tags, aliases, and cssclasses for Obsidian."""

import re

import yaml

from .pipeline import Transform

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _humanize_id(component_id: str) -> str:
    """auth-service -> Auth Service"""
    return component_id.replace("-", " ").replace("_", " ").title()


class FrontmatterFlattener(Transform):
    def apply(self, content: str, metadata: dict) -> str:
        if not metadata:
            return content

        fm = _build_frontmatter(metadata)
        dumped = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True).rstrip()

        new_block = f"---\n{dumped}\n---"

        # Replace existing frontmatter or prepend
        if _FRONTMATTER_RE.match(content):
            return _FRONTMATTER_RE.sub(new_block, content, count=1)
        return f"{new_block}\n\n{content}"


def _build_frontmatter(meta: dict) -> dict:
    component_id = meta.get("component_id", "")

    # Build tags: always start with tech-doc
    tags = ["tech-doc"]
    if layer := meta.get("layer"):
        tags.append(layer)
    if sec := meta.get("security_level"):
        tags.append(f"security-{sec}")
    if team := meta.get("owner_team"):
        tags.append(team)

    # Flatten governance dict
    governance = meta.get("governance", {})

    # Collect dependencies from edges
    edges = meta.get("edges", [])
    deps = [e["target"] for e in edges if "target" in e]

    fm: dict = {}
    if component_id:
        fm["title"] = _humanize_id(component_id)
        fm["aliases"] = [component_id]
    fm["tags"] = tags

    # Carry over scalar top-level fields
    for key in ("component_id", "version", "owner_team", "layer", "security_level"):
        if key in meta:
            fm[key] = meta[key]

    # Flatten governance keys to top level
    for k, v in governance.items():
        fm[k] = v

    if deps:
        fm["dependencies"] = deps

    fm["cssclass"] = "chronicler-doc"
    return fm
