"""OpenAI adapter for Chronicler."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig, LLMResponse, TokenUsage


class OpenAIProvider(LLMProvider):
    """OpenAI adapter using the async SDK."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key,  # falls back to OPENAI_API_KEY env var
            max_retries=2,
        )

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        if not response.choices:
            raise ValueError("No choices in OpenAI response")
        choice = response.choices[0]
        if not response.usage:
            raise ValueError("No usage data in OpenAI response")
        return LLMResponse(
            content=choice.message.content or "",
            usage=TokenUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            ),
            model=response.model,
        )

    async def generate_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.config.model,
            max_tokens=max_tokens,
            temperature=self.config.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
