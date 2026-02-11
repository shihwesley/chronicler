"""Auto-detect the best available LLM provider."""

from __future__ import annotations

import os

import httpx

from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.models import LLMConfig


def auto_detect_provider() -> LLMProvider:
    """Try providers in priority order and return the first available one.

    Order: Anthropic > OpenAI > Google Gemini > Ollama (local).
    Raises ValueError if nothing is available.
    """
    # 1. Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        from chronicler_core.llm.claude import ClaudeProvider

        return ClaudeProvider(
            LLMConfig(
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                api_key=api_key,
            )
        )

    # 2. OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        from chronicler_core.llm.openai_adapter import OpenAIProvider

        return OpenAIProvider(
            LLMConfig(
                provider="openai",
                model="gpt-4o",
                api_key=api_key,
            )
        )

    # 3. Google Gemini
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key:
        from chronicler_core.llm.gemini import GeminiProvider

        return GeminiProvider(
            LLMConfig(
                provider="google",
                model="gemini-2.0-flash",
                api_key=api_key,
            )
        )

    # 4. Ollama (local)
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        if models:
            from chronicler_core.llm.ollama import OllamaProvider

            return OllamaProvider(
                LLMConfig(
                    provider="ollama",
                    model=models[0]["name"],
                )
            )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        pass

    raise ValueError(
        "No LLM provider found. Set provider in chronicler.yaml or export an "
        "API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY) or start Ollama."
    )
