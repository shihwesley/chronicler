"""Ollama adapter for Chronicler."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig, LLMError, LLMResponse, TokenUsage

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """Ollama adapter using its REST API via httpx."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._base_url = (config.base_url or _DEFAULT_BASE_URL).rstrip("/")

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("message", {}).get("content", "")
            if not content:
                raise ValueError("No content in Ollama response")
            return LLMResponse(
                content=content,
                usage=TokenUsage(
                    input_tokens=data.get("prompt_eval_count", 0),
                    output_tokens=data.get("eval_count", 0),
                ),
                model=self.config.model,
            )
        except httpx.HTTPError as e:
            raise LLMError("ollama", "generate", e, retryable=False) from e

    async def generate_stream(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
        }
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=120.0,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError as e:
                            raise LLMError(
                                "ollama",
                                "generate_stream",
                                e,
                                retryable=False,
                            ) from e
                        text = data.get("message", {}).get("content", "")
                        if text:
                            yield text
        except httpx.HTTPError as e:
            raise LLMError("ollama", "generate_stream", e, retryable=False) from e
