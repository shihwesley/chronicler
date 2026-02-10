"""LLM provider abstraction layer."""

import os

from chronicler_core.config.models import LLMConfig as AppLLMConfig
from chronicler_core.llm.base import LLMProvider
from chronicler_core.llm.claude import ClaudeProvider
from chronicler_core.llm.gemini import GeminiProvider
from chronicler_core.llm.models import LLMConfig, LLMError, LLMResponse, TokenUsage
from chronicler_core.llm.ollama import OllamaProvider
from chronicler_core.llm.openai_adapter import OpenAIProvider

_PROVIDER_MAP: dict[str, type[LLMProvider]] = {
    "anthropic": ClaudeProvider,
    "openai": OpenAIProvider,
    "google": GeminiProvider,
    "ollama": OllamaProvider,
}


def create_llm_provider(config: AppLLMConfig) -> LLMProvider:
    """Create an LLM provider from app-level config.

    Resolves the API key from the env var in config.api_key_env, then
    bridges the app-level LLMConfig to the provider-level LLMConfig.
    For "auto" provider, delegates to auto_detect_provider().
    """
    if config.provider == "auto":
        from chronicler_core.llm.auto_detect import auto_detect_provider

        return auto_detect_provider()

    cls = _PROVIDER_MAP.get(config.provider)
    if cls is None:
        raise ValueError(
            f"Unsupported LLM provider: {config.provider!r}. "
            f"Supported: {', '.join(_PROVIDER_MAP)}"
        )

    # Ollama doesn't require an API key
    if config.provider == "ollama":
        llm_config = LLMConfig(
            provider=config.provider,
            model=config.model,
            max_tokens=config.max_tokens,
            base_url=config.base_url,
        )
        return cls(llm_config)

    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        raise ValueError(
            f"Missing API key: set environment variable {config.api_key_env!r}"
        )
    llm_config = LLMConfig(
        provider=config.provider,
        model=config.model,
        max_tokens=config.max_tokens,
        api_key=api_key,
        base_url=config.base_url,
    )
    return cls(llm_config)


__all__ = [
    "ClaudeProvider",
    "GeminiProvider",
    "LLMConfig",
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "OllamaProvider",
    "OpenAIProvider",
    "TokenUsage",
    "create_llm_provider",
]
