"""Ollama adapter for Chronicler."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import httpx

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"


def _validate_base_url(url: str) -> str:
    """Validate Ollama base_url for SSRF and injection risks.

    Raises ValueError if the URL is malformed or contains injection patterns.
    Warns if the URL is not localhost (remote Ollama is valid but uncommon).
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Ollama base_url must be http(s), got {parsed.scheme}")

    # Detect CRLF injection attempts
    if "\r" in url or "\n" in url:
        raise ValueError("CRLF injection detected in base_url")

    # Warn on non-localhost (but allow it — remote Ollama is valid)
    allowed_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if parsed.hostname not in allowed_hosts:
        logger.warning(
            "Ollama base_url %s is not localhost — ensure this is intentional",
            parsed.hostname
        )

    return url


class OllamaProvider(LLMProvider):
    """Ollama adapter using its REST API via httpx."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        raw_url = (config.base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._base_url = _validate_base_url(raw_url)

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
                    data = json.loads(line)
                    text = data.get("message", {}).get("content", "")
                    if text:
                        yield text
