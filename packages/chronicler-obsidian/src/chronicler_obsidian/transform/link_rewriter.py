"""Rewrites agent:// URIs to Obsidian [[wikilinks]]."""

import re

from .pipeline import Transform

# Matches agent://component_id or agent://component_id/path segments
_AGENT_URI_RE = re.compile(r"agent://([a-zA-Z0-9_-]+)(?:/([a-zA-Z0-9_./-]+))?")


class LinkRewriter(Transform):
    def apply(self, content: str, metadata: dict) -> str:
        return _AGENT_URI_RE.sub(_rewrite_match, content)


def _rewrite_match(m: re.Match) -> str:
    component = m.group(1)
    path = m.group(2)

    if path:
        # Strip .tech.md extension if present
        name = re.sub(r"\.tech\.md$", "", path)
        # Same-repo style: component - name
        link_text = f"{component} - {name}"
        return f"[[{link_text}]]"

    # Simple case: just the component_id
    return f"[[{component}]]"
