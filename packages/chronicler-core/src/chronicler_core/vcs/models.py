"""Pydantic models for VCS data."""

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class RepoMetadata(BaseModel):
    """Metadata for a repository."""

    component_id: str = Field(min_length=1, description="Unique identifier (owner/repo)")

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("component_id cannot be empty or whitespace")
        return v
    name: str
    full_name: str = Field(description="Full name including owner (e.g. owner/repo)")
    description: str | None = None
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Language breakdown in bytes (e.g. {'Python': 45000, 'Shell': 1200})",
    )
    default_branch: str = "main"
    size: int = 0
    topics: list[str] = Field(default_factory=list)
    url: str = ""

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if v == "":
            return v
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"url must use http or https scheme, got {parsed.scheme!r}")
        if not parsed.netloc:
            raise ValueError("url must have a valid host")
        return v


class FileNode(BaseModel):
    """A file or directory in a repository tree."""

    path: str
    name: str
    type: Literal["file", "dir"]
    size: int | None = None
    sha: str | None = None


class CrawlResult(BaseModel):
    """Result of crawling a single repository."""

    metadata: RepoMetadata
    tree: list[FileNode]
    key_files: dict[str, str] = Field(
        default_factory=dict, description="path -> content for key files"
    )
    converted_docs: dict[str, str] = Field(
        default_factory=dict, description="path -> markdown for converted documents"
    )
