"""Pydantic models for the LLM subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: Literal["anthropic", "openai", "google"]
    model: str
    max_tokens: int = 4096
    temperature: float = 0.3
    api_key: str | None = None


class TokenUsage(BaseModel):
    """Token usage stats from a single LLM call."""

    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    """Structured response from an LLM provider."""

    content: str
    usage: TokenUsage
    model: str
