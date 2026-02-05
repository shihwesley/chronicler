"""Pydantic models for VCS data."""

from typing import Literal

from pydantic import BaseModel, Field


class RepoMetadata(BaseModel):
    """Metadata for a repository."""

    component_id: str = Field(description="Unique identifier (owner/repo)")
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
