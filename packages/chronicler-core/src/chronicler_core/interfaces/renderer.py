"""Renderer plugin interface and models."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class RenderFormat(str, Enum):
    """Output formats supported by renderer plugins."""

    svg = "svg"
    png = "png"
    ascii = "ascii"
    html = "html"


@runtime_checkable
class RendererPlugin(Protocol):
    """Renderer for diagram blocks within .tech.md content."""

    def render(self, source: str, format: RenderFormat) -> str: ...

    def supported_types(self) -> list[str]: ...
