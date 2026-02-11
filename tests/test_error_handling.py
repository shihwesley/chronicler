"""Error handling tests for all error-path changes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from anthropic import APIError as AnthropicAPIError
from anthropic import RateLimitError as AnthropicRateLimitError

from openai import APIError as OpenAIAPIError
from openai import RateLimitError as OpenAIRateLimitError

from chronicler_core.config.loader import _expand_env_vars
from chronicler_core.config.models import OutputConfig
from chronicler_core.drafter.models import FrontmatterModel, TechDoc
from chronicler_core.freshness.watcher import _DebouncedHandler, _MAX_STALE
from chronicler_core.llm.claude import ClaudeProvider
from chronicler_core.llm.gemini import GeminiProvider
from chronicler_core.llm.models import LLMConfig, LLMError
from chronicler_core.llm.ollama import OllamaProvider
from chronicler_core.llm.openai_adapter import OpenAIProvider
from chronicler_core.merkle.scanner import MercatorScanner
from chronicler_core.output.writer import TechMdWriter
from chronicler_core.plugins.loader import PluginLoader
# Import _split_frontmatter lazily to avoid memvid module loading side effects


# ========================================================================
# LLM Error Handling Tests
# ========================================================================


@pytest.mark.asyncio
async def test_claude_provider_wraps_api_error():
    """Claude adapter wraps APIError in LLMError."""
    config = LLMConfig(provider="anthropic", model="test", api_key="test")
    provider = ClaudeProvider(config)

    with patch.object(
        provider._client.messages, "create", side_effect=AnthropicAPIError(
            message="test error", request=Mock(), body=None
        )
    ):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.provider == "claude"
        assert exc_info.value.operation == "generate"
        assert not exc_info.value.retryable
        assert isinstance(exc_info.value.__cause__, AnthropicAPIError)


@pytest.mark.asyncio
async def test_claude_provider_marks_rate_limit_retryable():
    """Claude adapter marks RateLimitError as retryable."""
    config = LLMConfig(provider="anthropic", model="test", api_key="test")
    provider = ClaudeProvider(config)

    with patch.object(
        provider._client.messages,
        "create",
        side_effect=AnthropicRateLimitError(
            message="rate limit", response=Mock(), body=None
        ),
    ):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.retryable


@pytest.mark.asyncio
async def test_openai_provider_wraps_api_error():
    """OpenAI adapter wraps APIError in LLMError."""
    config = LLMConfig(provider="openai", model="test", api_key="test")
    provider = OpenAIProvider(config)

    with patch.object(
        provider._client.chat.completions,
        "create",
        side_effect=OpenAIAPIError(
            message="test error", request=Mock(), body=None
        ),
    ):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.provider == "openai"
        assert exc_info.value.operation == "generate"
        assert not exc_info.value.retryable


@pytest.mark.asyncio
async def test_openai_provider_marks_rate_limit_retryable():
    """OpenAI adapter marks RateLimitError as retryable."""
    config = LLMConfig(provider="openai", model="test", api_key="test")
    provider = OpenAIProvider(config)

    with patch.object(
        provider._client.chat.completions,
        "create",
        side_effect=OpenAIRateLimitError(
            message="rate limit", response=Mock(), body=None
        ),
    ):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.retryable


@pytest.mark.asyncio
async def test_gemini_provider_wraps_api_error():
    """Gemini adapter wraps exceptions in LLMError."""
    config = LLMConfig(provider="google", model="test", api_key="test")
    provider = GeminiProvider(config)

    with patch.object(
        provider._client.aio.models, "generate_content",
        new=AsyncMock(side_effect=RuntimeError("connection failed")),
    ):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.provider == "gemini"
        assert exc_info.value.operation == "generate"
        assert not exc_info.value.retryable


@pytest.mark.asyncio
async def test_gemini_provider_marks_rate_limit_retryable():
    """Gemini adapter marks 429 errors as retryable."""
    config = LLMConfig(provider="google", model="test", api_key="test")
    provider = GeminiProvider(config)

    with patch.object(
        provider._client.aio.models, "generate_content",
        new=AsyncMock(side_effect=RuntimeError("429 Resource exhausted")),
    ):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.retryable


@pytest.mark.asyncio
async def test_ollama_provider_wraps_http_error():
    """Ollama adapter wraps httpx.HTTPError in LLMError."""
    config = LLMConfig(provider="ollama", model="test")
    provider = OllamaProvider(config)

    import httpx

    with patch("httpx.AsyncClient.post", side_effect=httpx.HTTPError("network error")):
        with pytest.raises(LLMError) as exc_info:
            await provider.generate("system", "user")

        assert exc_info.value.provider == "ollama"
        assert exc_info.value.operation == "generate"
        assert not exc_info.value.retryable


@pytest.mark.asyncio
async def test_ollama_stream_json_parse_error():
    """Ollama stream wraps json.JSONDecodeError in LLMError."""
    config = LLMConfig(provider="ollama", model="test")
    provider = OllamaProvider(config)

    async def mock_lines():
        yield "invalid json"

    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.aiter_lines = mock_lines

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value.__aenter__.return_value = mock_response

        with pytest.raises(LLMError) as exc_info:
            async for _ in provider.generate_stream("system", "user"):
                pass

        assert exc_info.value.provider == "ollama"
        assert exc_info.value.operation == "generate_stream"
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


# ========================================================================
# File I/O Error Handling Tests
# ========================================================================


def test_writer_handles_oserror_on_write(tmp_path):
    """TechMdWriter logs error and raises OSError on write failure."""
    config = OutputConfig(base_dir=str(tmp_path))
    writer = TechMdWriter(config)
    doc = TechDoc(component_id="test", frontmatter=FrontmatterModel(component_id="test"), raw_content="content")

    # Patch write_text to raise OSError instead of relying on file permissions
    with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            writer.write(doc)


def test_writer_handles_yaml_parse_error_on_index_read(tmp_path, caplog):
    """TechMdWriter warns on YAML parse error in index read."""
    config = OutputConfig(base_dir=str(tmp_path), create_index=True)
    writer = TechMdWriter(config)

    # Write invalid YAML to index
    index_path = tmp_path / "_index.yaml"
    index_path.write_text("invalid: yaml: [unclosed", encoding="utf-8")

    doc = TechDoc(component_id="test", frontmatter=FrontmatterModel(component_id="test"), raw_content="content")
    writer.write(doc)

    assert any("Failed to parse index" in rec.message for rec in caplog.records)


def test_writer_handles_oserror_on_index_read(tmp_path, caplog):
    """TechMdWriter warns on OSError during index read."""
    config = OutputConfig(base_dir=str(tmp_path), create_index=True)
    writer = TechMdWriter(config)

    # Create an index file first so exists() returns True
    index_path = tmp_path / "_index.yaml"
    index_path.write_text("[]")

    doc = TechDoc(component_id="test", frontmatter=FrontmatterModel(component_id="test"), raw_content="content")

    original_read = Path.read_text
    def selective_read(self, *args, **kwargs):
        if self.name == "_index.yaml":
            raise OSError("permission denied")
        return original_read(self, *args, **kwargs)

    with patch.object(Path, "read_text", selective_read):
        writer.write(doc)

    assert any("Failed to read index" in rec.message for rec in caplog.records)


# ========================================================================
# Merkle Scanner Error Handling Tests
# ========================================================================


def test_scanner_fallback_diff_handles_json_decode_error(tmp_path, caplog):
    """MercatorScanner._fallback_diff warns and treats invalid JSON as empty manifest."""
    from chronicler_core.config.models import MerkleConfig

    config = MerkleConfig()
    scanner = MercatorScanner(config)

    manifest = tmp_path / "manifest.json"
    manifest.write_text("invalid json{", encoding="utf-8")

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")

    result = scanner._fallback_diff(tmp_path, manifest)

    assert result.has_changes
    assert "test.txt" in result.added
    assert any("Failed to parse manifest" in rec.message for rec in caplog.records)


def test_scanner_fallback_diff_handles_oserror(tmp_path, caplog):
    """MercatorScanner._fallback_diff warns and treats missing file as empty manifest."""
    from chronicler_core.config.models import MerkleConfig

    config = MerkleConfig()
    scanner = MercatorScanner(config)

    manifest = tmp_path / "nonexistent.json"

    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")

    result = scanner._fallback_diff(tmp_path, manifest)

    assert result.has_changes
    assert "test.txt" in result.added
    assert any("Failed to parse manifest" in rec.message for rec in caplog.records)


# ========================================================================
# Config Loader Error Handling Tests
# ========================================================================


def test_expand_env_vars_raises_on_missing_var():
    """_expand_env_vars raises ValueError when env var is missing."""
    # Use an allowlisted var that's not set
    os.environ.pop("ANTHROPIC_API_KEY", None)

    with pytest.raises(ValueError) as exc_info:
        _expand_env_vars({"key": "${ANTHROPIC_API_KEY}"})

    assert "ANTHROPIC_API_KEY" in str(exc_info.value)
    assert "not set" in str(exc_info.value)


def test_expand_env_vars_expands_existing_var():
    """_expand_env_vars expands when env var exists."""
    os.environ["ANTHROPIC_API_KEY"] = "test_value"
    try:
        result = _expand_env_vars({"key": "${ANTHROPIC_API_KEY}"})
        assert result == {"key": "test_value"}
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)


def test_expand_env_vars_nested_structure():
    """_expand_env_vars raises on missing var in nested structure."""
    os.environ.pop("GITHUB_TOKEN", None)

    with pytest.raises(ValueError):
        _expand_env_vars({"outer": {"inner": ["${GITHUB_TOKEN}"]}})


# ========================================================================
# Plugin Loader Error Handling Tests
# ========================================================================


def test_plugin_loader_logs_warning_on_import_failure(caplog):
    """PluginLoader logs warning when Lite default import fails."""
    from chronicler_core.config.models import ChroniclerConfig

    config = ChroniclerConfig()
    loader = PluginLoader(config)

    # Patch LITE_DEFAULTS to reference a non-existent module
    with patch.dict(
        loader.LITE_DEFAULTS, {"queue": ("nonexistent_module", "FakeClass")}
    ):
        result = loader._load_lite_default("queue")

        assert result is None
        assert any("Failed to import Lite default" in rec.message for rec in caplog.records)


# ========================================================================
# MemVid Storage Error Handling Tests
# ========================================================================


def test_split_frontmatter_logs_warning_on_yaml_error(caplog):
    """_split_frontmatter logs warning on invalid YAML."""
    from chronicler_lite.storage.memvid_storage import _split_frontmatter

    text = "---\ninvalid: yaml: [unclosed\n---\nbody"

    fm, body = _split_frontmatter(text)

    assert fm == {}
    assert body == text
    assert any("Failed to parse YAML frontmatter" in rec.message for rec in caplog.records)


# ========================================================================
# Freshness Watcher Error Handling Tests
# ========================================================================


def test_watcher_bounds_stale_set():
    """FreshnessWatcher bounds stale set to _MAX_STALE entries."""
    import threading

    stale_paths: set[str] = set()
    lock = threading.Lock()

    handler = _DebouncedHandler(
        debounce_seconds=0.0, stale_paths=stale_paths, lock=lock, callback=None
    )

    # Pre-fill to just under max
    with lock:
        for i in range(_MAX_STALE - 1):
            stale_paths.add(f"path_{i}")

    # Simulate events beyond max
    from watchdog.events import FileModifiedEvent

    for i in range(10):
        event = FileModifiedEvent(f"/tmp/new_path_{i}")
        handler.on_any_event(event)

    with lock:
        assert len(stale_paths) <= _MAX_STALE
