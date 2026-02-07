"""LLM provider abstraction layer."""

import os

from chronicler.config.models import LLMConfig as AppLLMConfig
from chronicler.llm.base import LLMProvider
from chronicler.llm.claude import ClaudeProvider
from chronicler.llm.models import LLMConfig, LLMResponse, TokenUsage
from chronicler.llm.openai_adapter import OpenAIProvider

_PROVIDER_MAP: dict[str, type[LLMProvider]] = {
    "anthropic": ClaudeProvider,
    "openai": OpenAIProvider,
}


def create_llm_provider(config: AppLLMConfig) -> LLMProvider:
    """Create an LLM provider from app-level config.

    Resolves the API key from the env var in config.api_key_env, then
    bridges the app-level LLMConfig to the provider-level LLMConfig.
    """
    cls = _PROVIDER_MAP.get(config.provider)
    if cls is None:
        raise ValueError(
            f"Unsupported LLM provider: {config.provider!r}. "
            f"Supported: {', '.join(_PROVIDER_MAP)}"
        )
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
    )
    return cls(llm_config)


__all__ = [
    "ClaudeProvider",
    "LLMConfig",
    "LLMProvider",
    "LLMResponse",
    "OpenAIProvider",
    "TokenUsage",
    "create_llm_provider",
]
