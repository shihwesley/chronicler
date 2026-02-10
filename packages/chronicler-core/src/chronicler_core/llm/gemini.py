"""Google Gemini adapter for Chronicler."""

from __future__ import annotations

from collections.abc import AsyncIterator

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig, LLMError, LLMResponse, TokenUsage


class GeminiProvider(LLMProvider):
    """Gemini adapter using the google-generativeai async SDK."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        genai.configure(api_key=config.api_key)
        self._model = genai.GenerativeModel(config.model)

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            response = await self._model.generate_content_async(
                f"{system}\n\n{user}",
                generation_config=genai.types.GenerationConfig(
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
        except google_exceptions.GoogleAPIError as e:
            raise LLMError(
                "gemini",
                "generate",
                e,
                retryable=isinstance(e, google_exceptions.ResourceExhausted),
            ) from e

    async def generate_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        try:
            response = await self._model.generate_content_async(
                f"{system}\n\n{user}",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=self.config.temperature,
                ),
                stream=True,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except google_exceptions.GoogleAPIError as e:
            raise LLMError(
                "gemini",
                "generate_stream",
                e,
                retryable=isinstance(e, google_exceptions.ResourceExhausted),
            ) from e
