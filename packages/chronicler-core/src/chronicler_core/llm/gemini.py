"""Google Gemini adapter for Chronicler."""

from __future__ import annotations

from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig, LLMError, LLMResponse, TokenUsage


class GeminiProvider(LLMProvider):
    """Gemini adapter using the google-genai async SDK."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client = genai.Client(api_key=config.api_key)

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            response = await self._client.aio.models.generate_content(
                model=self.config.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    temperature=self.config.temperature,
                ),
            )
            if not response.text:
                raise ValueError("No text content in Gemini response")
            usage = response.usage_metadata
            return LLMResponse(
                content=response.text,
                usage=TokenUsage(
                    input_tokens=usage.prompt_token_count,
                    output_tokens=usage.candidates_token_count,
                ),
                model=self.config.model,
            )
        except Exception as e:
            raise LLMError(
                "gemini",
                "generate",
                e,
                retryable="429" in str(e) or "503" in str(e),
            ) from e

    async def generate_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        try:
            async for chunk in self._client.aio.models.generate_content_stream(
                model=self.config.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    temperature=self.config.temperature,
                ),
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise LLMError(
                "gemini",
                "generate_stream",
                e,
                retryable="429" in str(e) or "503" in str(e),
            ) from e
