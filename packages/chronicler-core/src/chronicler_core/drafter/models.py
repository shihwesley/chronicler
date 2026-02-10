"""Pydantic models for the drafter subsystem."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class GovernanceModel(BaseModel):
    """Governance metadata within frontmatter."""

    business_impact: str | None = None
    verification_status: str = "ai_draft"
    visibility: str = "internal"


class FrontmatterModel(BaseModel):
    """Typed frontmatter for .tech.md files."""

    component_id: str = Field(min_length=1)
    version: str = "0.1.0"
    owner_team: str = "unknown"
    layer: str = "unknown"
    security_level: str = "low"
    governance: GovernanceModel = Field(default_factory=GovernanceModel)
    edges: list[Any] = Field(default_factory=list)

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("component_id cannot be empty or whitespace")
        return v


class TechDoc(BaseModel):
    """Complete .tech.md document."""

    component_id: str = Field(min_length=1)
    frontmatter: FrontmatterModel

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("component_id cannot be empty or whitespace")
        return v
    architectural_intent: str = ""
    connectivity_graph: str = ""
    raw_content: str = ""
