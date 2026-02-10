"""Tests for Gemini, Ollama adapters and auto-detection logic."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from chronicler_core.config.models import LLMSettings as AppLLMSettings
from chronicler_core.llm import create_llm_provider
from chronicler_core.llm.auto_detect import auto_detect_provider
from chronicler_core.llm.claude import ClaudeProvider
from chronicler_core.llm.gemini import GeminiProvider
from chronicler_core.llm.models import LLMConfig, LLMResponse, TokenUsage
from chronicler_core.llm.ollama import OllamaProvider
from chronicler_core.llm.openai_adapter import OpenAIProvider


# ---------------------------------------------------------------------------
# create_llm_provider — new providers
# ---------------------------------------------------------------------------


class TestCreateLLMProviderNew:
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "goog-key-123"})
    @patch("chronicler_core.llm.gemini.genai")
    def test_creates_gemini_provider(self, mock_genai):
        config = AppLLMSettings(
            provider="google",
            model="gemini-2.0-flash",
            api_key_env="GOOGLE_API_KEY",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, GeminiProvider)

    def test_creates_ollama_provider(self):
        config = AppLLMSettings(
            provider="ollama",
            model="llama3",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, OllamaProvider)

    def test_ollama_provider_custom_base_url(self):
        config = AppLLMSettings(
            provider="ollama",
            model="llama3",
            base_url="http://myhost:11434",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, OllamaProvider)
        assert provider._base_url == "http://myhost:11434"


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


class TestAutoDetect:
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_picks_claude_when_anthropic_key_set(self):
        provider = auto_detect_provider()
        assert isinstance(provider, ClaudeProvider)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=True)
    def test_picks_openai_when_only_openai_key(self):
        provider = auto_detect_provider()
        assert isinstance(provider, OpenAIProvider)

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "goog-key"}, clear=True)
    @patch("chronicler_core.llm.gemini.genai")
    def test_picks_gemini_when_only_google_key(self, mock_genai):
        provider = auto_detect_provider()
        assert isinstance(provider, GeminiProvider)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "gem-key"}, clear=True)
    @patch("chronicler_core.llm.gemini.genai")
    def test_picks_gemini_with_gemini_api_key(self, mock_genai):
        provider = auto_detect_provider()
        assert isinstance(provider, GeminiProvider)

    @patch.dict(os.environ, {}, clear=True)
    @patch("chronicler_core.llm.auto_detect.httpx")
    def test_picks_ollama_when_running(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "llama3:latest"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp
        # Need to expose the exceptions so the except clause works
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError

        provider = auto_detect_provider()
        assert isinstance(provider, OllamaProvider)
        assert provider.config.model == "llama3:latest"

    @patch.dict(os.environ, {}, clear=True)
    @patch("chronicler_core.llm.auto_detect.httpx")
    def test_raises_when_nothing_available(self, mock_httpx):
        mock_httpx.get.side_effect = httpx.ConnectError("refused")
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError

        with pytest.raises(ValueError, match="No LLM provider found"):
            auto_detect_provider()

    @patch.dict(
        os.environ,
        {"ANTHROPIC_API_KEY": "ant", "OPENAI_API_KEY": "oai"},
        clear=True,
    )
    def test_prefers_anthropic_over_openai(self):
        provider = auto_detect_provider()
        assert isinstance(provider, ClaudeProvider)


# ---------------------------------------------------------------------------
# OllamaProvider.generate() — mocked httpx
# ---------------------------------------------------------------------------


class TestOllamaProviderGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_response(self):
        config = LLMConfig(provider="ollama", model="llama3")
        provider = OllamaProvider(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Hello from Ollama"},
            "prompt_eval_count": 10,
            "eval_count": 25,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("chronicler_core.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            result = await provider.generate("system prompt", "user message")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from Ollama"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 25
        assert result.model == "llama3"

    @pytest.mark.asyncio
    async def test_generate_raises_on_empty_content(self):
        config = LLMConfig(provider="ollama", model="llama3")
        provider = OllamaProvider(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": ""}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("chronicler_core.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="No content in Ollama response"):
                await provider.generate("sys", "usr")


# ---------------------------------------------------------------------------
# GeminiProvider.generate() — mocked genai
# ---------------------------------------------------------------------------


class TestGeminiProviderGenerate:
    @pytest.mark.asyncio
    @patch("chronicler_core.llm.gemini.genai")
    async def test_generate_returns_response(self, mock_genai):
        # Set up the mock model and its async generate call
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 15
        mock_usage.candidates_token_count = 42

        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini"
        mock_response.usage_metadata = mock_usage

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        mock_genai.GenerativeModel.return_value = mock_model

        config = LLMConfig(provider="google", model="gemini-2.0-flash", api_key="fake")
        provider = GeminiProvider(config)

        result = await provider.generate("system prompt", "user message")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from Gemini"
        assert result.usage.input_tokens == 15
        assert result.usage.output_tokens == 42
        assert result.model == "gemini-2.0-flash"

    @pytest.mark.asyncio
    @patch("chronicler_core.llm.gemini.genai")
    async def test_generate_raises_on_empty_text(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = ""

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        mock_genai.GenerativeModel.return_value = mock_model

        config = LLMConfig(provider="google", model="gemini-2.0-flash", api_key="fake")
        provider = GeminiProvider(config)

        with pytest.raises(ValueError, match="No text content in Gemini response"):
            await provider.generate("sys", "usr")
