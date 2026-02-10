"""Anthropic Claude adapter for Chronicler."""

from __future__ import annotations

from collections.abc import AsyncIterator

from anthropic import APIError, AsyncAnthropic, RateLimitError

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig, LLMError, LLMResponse, TokenUsage


class ClaudeProvider(LLMProvider):
    """Claude adapter using the Anthropic async SDK."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client = AsyncAnthropic(
            api_key=config.api_key,  # falls back to ANTHROPIC_API_KEY env var
            max_retries=2,
        )

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            message = await self._client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens,
                temperature=self.config.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if not message.content or not hasattr(message.content[0], "text"):
                raise ValueError("No text content in Claude response")
            return LLMResponse(
                content=message.content[0].text,
                usage=TokenUsage(
                    input_tokens=message.usage.input_tokens,
                    output_tokens=message.usage.output_tokens,
                ),
                model=message.model,
            )
        except APIError as e:
            raise LLMError(
                "claude", "generate", e, retryable=isinstance(e, RateLimitError)
            ) from e

    async def generate_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        try:
            async with self._client.messages.stream(
                model=self.config.model,
                max_tokens=max_tokens,
                temperature=self.config.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except APIError as e:
            raise LLMError(
                "claude", "generate_stream", e, retryable=isinstance(e, RateLimitError)
            ) from e
