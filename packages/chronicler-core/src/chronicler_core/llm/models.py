"""Pydantic models for the LLM subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LLMError(Exception):
    """Wraps provider-specific exceptions with context."""

    def __init__(
        self, provider: str, operation: str, cause: Exception, retryable: bool = False
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.retryable = retryable
        super().__init__(f"{provider} {operation} failed: {cause}")
        self.__cause__ = cause


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: Literal["anthropic", "openai", "google", "ollama", "auto"]
    model: str
    max_tokens: int = 4096
    temperature: float = 0.3
    api_key: str | None = None
    base_url: str | None = None


class TokenUsage(BaseModel):
    """Token usage stats from a single LLM call."""

    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    """Structured response from an LLM provider."""

    content: str
    usage: TokenUsage
    model: str
