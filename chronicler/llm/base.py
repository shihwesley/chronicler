"""Abstract LLM interface for Chronicler."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from chronicler.llm.models import LLMConfig, LLMResponse


class LLMProvider(ABC):
    """Provider-agnostic interface for long-form document generation.

    Every adapter must implement both one-shot and streaming generation,
    since Chronicler drafts full .tech.md files (1500+ words) and needs
    streaming for real-time progress feedback.
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a complete response (one-shot)."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Yield response text chunks as they arrive."""
        ...
