"""Tests for the LLM subsystem: provider factory and model classes."""

import os
import pytest
from unittest.mock import patch, MagicMock

from chronicler_core.config.models import LLMConfig as AppLLMConfig
from chronicler_core.llm import create_llm_provider, LLMConfig, LLMResponse, TokenUsage
from chronicler_core.llm.claude import ClaudeProvider
from chronicler_core.llm.openai_adapter import OpenAIProvider


# ---------------------------------------------------------------------------
# Model smoke tests
# ---------------------------------------------------------------------------


class TestLLMModels:
    def test_token_usage(self):
        usage = TokenUsage(input_tokens=100, output_tokens=200)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 200

    def test_llm_response(self):
        resp = LLMResponse(
            content="hello",
            usage=TokenUsage(input_tokens=10, output_tokens=20),
            model="test-model",
        )
        assert resp.content == "hello"
        assert resp.model == "test-model"

    def test_llm_config_defaults(self):
        cfg = LLMConfig(provider="anthropic", model="claude-3")
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.3
        assert cfg.api_key is None


# ---------------------------------------------------------------------------
# create_llm_provider
# ---------------------------------------------------------------------------


class TestCreateLLMProvider:
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"})
    def test_creates_claude_provider(self):
        config = AppLLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key_env="ANTHROPIC_API_KEY",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, ClaudeProvider)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    def test_creates_openai_provider(self):
        config = AppLLMConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, OpenAIProvider)

    def test_unsupported_provider_raises(self):
        config = AppLLMConfig(
            provider="anthropic",
            model="test",
            api_key_env="SOME_KEY",
        )
        # Monkey-patch provider to something unsupported
        object.__setattr__(config, "provider", "unsupported_llm")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_provider(config)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises(self):
        config = AppLLMConfig(
            provider="anthropic",
            model="test",
            api_key_env="NONEXISTENT_KEY_VAR",
        )
        # Remove the env var if it somehow exists
        os.environ.pop("NONEXISTENT_KEY_VAR", None)
        with pytest.raises(ValueError, match="Missing API key"):
            create_llm_provider(config)

    @patch.dict(os.environ, {"MY_KEY": "abc"})
    def test_custom_api_key_env(self):
        config = AppLLMConfig(
            provider="anthropic",
            model="test",
            api_key_env="MY_KEY",
        )
        provider = create_llm_provider(config)
        assert provider.config.api_key == "abc"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key123"})
    def test_provider_config_has_correct_model(self):
        config = AppLLMConfig(
            provider="anthropic",
            model="claude-opus-4-20250514",
            api_key_env="ANTHROPIC_API_KEY",
        )
        provider = create_llm_provider(config)
        assert provider.config.model == "claude-opus-4-20250514"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key123"})
    def test_provider_config_max_tokens(self):
        config = AppLLMConfig(
            provider="anthropic",
            model="test",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=8192,
        )
        provider = create_llm_provider(config)
        assert provider.config.max_tokens == 8192
