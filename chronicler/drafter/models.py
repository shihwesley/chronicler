"""Pydantic models for the drafter subsystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TruncationConfig(BaseModel):
    """Limits for context window management."""

    max_readme_chars: int = 2000
    max_file_tree_files: int = 50
    max_dockerfile_chars: int = 1000
    max_description_chars: int = 500


class PromptContext(BaseModel):
    """Structured repo context for LLM prompt injection."""

    repo_name: str
    description: str | None = None
    default_branch: str = "main"
    languages: str = ""
    topics: str = ""
    file_tree: str = ""
    readme_content: str = ""
    package_json: str = ""
    dockerfile: str = ""
    dependencies_list: str = ""
    converted_docs_summary: str = ""


class TechDoc(BaseModel):
    """Complete .tech.md document."""

    component_id: str
    frontmatter: dict = Field(default_factory=dict)
    architectural_intent: str = ""
    connectivity_graph: str = ""
    raw_content: str = ""
