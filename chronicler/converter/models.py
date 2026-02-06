"""Pydantic models for the document conversion subsystem."""

from __future__ import annotations

from pydantic import BaseModel


class ConversionResult(BaseModel):
    """Result of converting a document to markdown."""

    source_path: str
    markdown: str
    format: str  # pdf, docx, etc.
    cached: bool = False
