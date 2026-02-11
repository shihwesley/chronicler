"""Tests for chronicler.config — models and YAML loader."""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from chronicler_core.config.models import (
    ChroniclerConfig,
    DocumentConversionConfig,
    FormatConfig,
    LLMSettings,
    MonorepoConfig,
    OCRConfig,
    OutputConfig,
    QueueConfig,
    VCSConfig,
)
from chronicler_core.config.loader import load_config, _expand_env_vars


# ── ChroniclerConfig defaults ──────────────────────────────────────


class TestChroniclerConfigDefaults:
    def test_default_log_level(self, sample_config):
        assert sample_config.log_level == "info"

    def test_default_log_format(self, sample_config):
        assert sample_config.log_format == "text"

    def test_default_llm_provider(self, sample_config):
        assert sample_config.llm.provider == "anthropic"

    def test_default_vcs_provider(self, sample_config):
        assert sample_config.vcs.provider == "github"

    def test_default_output_base_dir(self, sample_config):
        assert sample_config.output.base_dir == ".chronicler"

    def test_default_queue_provider(self, sample_config):
        assert sample_config.queue.provider == "local"

    def test_default_monorepo_detection(self, sample_config):
        assert sample_config.monorepo.detection == "auto"

    def test_default_document_conversion_enabled(self, sample_config):
        assert sample_config.document_conversion.enabled is True


# ── Individual config model validations ─────────────────────────────


class TestLLMSettings:
    def test_defaults(self):
        cfg = LLMSettings()
        assert cfg.model == "claude-haiku-4-5-20251001"
        assert cfg.max_tokens == 4096
        assert cfg.timeout == 60
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 1.0

    def test_invalid_provider_rejected(self):
        with pytest.raises(ValidationError):
            LLMSettings(provider="badprovider")

    def test_custom_values(self):
        cfg = LLMSettings(provider="openai", model="gpt-4o", max_tokens=8192)
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.max_tokens == 8192


class TestVCSConfig:
    def test_defaults(self):
        cfg = VCSConfig()
        assert cfg.provider == "github"
        assert cfg.token_env == "GITHUB_TOKEN"
        assert cfg.allowed_orgs == []
        assert cfg.rate_limit_buffer == 100

    def test_invalid_provider_rejected(self):
        with pytest.raises(ValidationError):
            VCSConfig(provider="bitbucket")

    def test_allowed_orgs(self):
        cfg = VCSConfig(allowed_orgs=["acme", "widgets-inc"])
        assert len(cfg.allowed_orgs) == 2


class TestQueueConfig:
    def test_defaults(self):
        cfg = QueueConfig()
        assert cfg.provider == "local"
        assert cfg.url is None
        assert cfg.max_workers == 5

    def test_sqs_config(self):
        cfg = QueueConfig(provider="sqs", url="https://sqs.us-east-1.amazonaws.com/123/my-queue")
        assert cfg.provider == "sqs"
        assert cfg.url is not None


class TestOutputConfig:
    def test_defaults(self):
        cfg = OutputConfig()
        assert cfg.base_dir == ".chronicler"
        assert cfg.create_index is True
        assert cfg.validation == "strict"

    def test_invalid_validation_mode(self):
        with pytest.raises(ValidationError):
            OutputConfig(validation="none")


class TestMonorepoConfig:
    def test_defaults(self):
        cfg = MonorepoConfig()
        assert cfg.detection == "auto"
        assert "packages" in cfg.package_dirs

    def test_invalid_detection_mode(self):
        with pytest.raises(ValidationError):
            MonorepoConfig(detection="full-scan")


class TestDocumentConversionConfig:
    def test_defaults(self):
        cfg = DocumentConversionConfig()
        assert cfg.enabled is True
        assert cfg.max_file_size_mb == 50
        assert cfg.max_pages == 100

    def test_nested_formats(self):
        cfg = DocumentConversionConfig()
        assert cfg.formats.pdf is True
        assert cfg.formats.xlsx is False

    def test_nested_ocr(self):
        cfg = DocumentConversionConfig()
        assert cfg.ocr.enabled is True
        assert cfg.ocr.use_llm is False

    def test_nested_cache(self):
        cfg = DocumentConversionConfig()
        assert cfg.cache.enabled is True
        assert cfg.cache.ttl_days == 7


# ── _expand_env_vars ────────────────────────────────────────────────


class TestExpandEnvVars:
    def test_expands_string_variable(self):
        from chronicler_core.config.loader import _ALLOWED_ENV_VARS
        with patch("chronicler_core.config.loader._ALLOWED_ENV_VARS", _ALLOWED_ENV_VARS | {"MY_KEY"}):
            with patch.dict(os.environ, {"MY_KEY": "secret123"}):
                assert _expand_env_vars("${MY_KEY}") == "secret123"

    def test_missing_var_becomes_empty(self):
        # Use an allowlisted var that's not set
        os.environ.pop("ANTHROPIC_API_KEY", None)
        # Now it should raise because it's not set (not because it's not in allowlist)
        # Old behavior: returned "". New behavior: raises ValueError
        # Update test to match new stricter behavior
        with pytest.raises(ValueError, match="not set"):
            _expand_env_vars("${ANTHROPIC_API_KEY}")

    def test_expands_in_dict(self):
        from chronicler_core.config.loader import _ALLOWED_ENV_VARS
        with patch("chronicler_core.config.loader._ALLOWED_ENV_VARS", _ALLOWED_ENV_VARS | {"TOKEN"}):
            with patch.dict(os.environ, {"TOKEN": "abc"}):
                result = _expand_env_vars({"key": "${TOKEN}"})
                assert result == {"key": "abc"}

    def test_expands_in_list(self):
        from chronicler_core.config.loader import _ALLOWED_ENV_VARS
        with patch("chronicler_core.config.loader._ALLOWED_ENV_VARS", _ALLOWED_ENV_VARS | {"X"}):
            with patch.dict(os.environ, {"X": "1"}):
                result = _expand_env_vars(["${X}", "literal"])
                assert result == ["1", "literal"]

    def test_expands_nested_structures(self):
        from chronicler_core.config.loader import _ALLOWED_ENV_VARS
        with patch("chronicler_core.config.loader._ALLOWED_ENV_VARS", _ALLOWED_ENV_VARS | {"A", "B"}):
            with patch.dict(os.environ, {"A": "alpha", "B": "beta"}):
                result = _expand_env_vars({"outer": {"inner": "${A}"}, "list": ["${B}"]})
                assert result == {"outer": {"inner": "alpha"}, "list": ["beta"]}

    def test_non_string_passthrough(self):
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None

    def test_mixed_text_and_var(self):
        from chronicler_core.config.loader import _ALLOWED_ENV_VARS
        with patch("chronicler_core.config.loader._ALLOWED_ENV_VARS", _ALLOWED_ENV_VARS | {"HOST"}):
            with patch.dict(os.environ, {"HOST": "localhost"}):
                assert _expand_env_vars("http://${HOST}:8080") == "http://localhost:8080"


# ── load_config ─────────────────────────────────────────────────────


class TestLoadConfig:
    def test_returns_defaults_when_no_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # No chronicler.yaml, no home config — should get defaults
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")
        config = load_config()
        assert config.llm.provider == "anthropic"
        assert config.log_level == "info"

    def test_loads_valid_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_file = tmp_path / "chronicler.yaml"
        yaml_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4o\nlog_level: debug\n"
        )
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")
        config = load_config()
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.log_level == "debug"

    def test_raises_on_invalid_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_file = tmp_path / "chronicler.yaml"
        yaml_file.write_text("  bad:\nyaml: [unterminated")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config()

    def test_raises_on_invalid_config_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_file = tmp_path / "chronicler.yaml"
        yaml_file.write_text("llm:\n  provider: badprovider\n")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")
        with pytest.raises(ValueError, match="Invalid config"):
            load_config()

    def test_cli_path_takes_priority(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Project-local config says openai
        project_file = tmp_path / "chronicler.yaml"
        project_file.write_text("llm:\n  provider: openai\n  model: gpt-4o\n")
        # CLI config says google
        cli_file = tmp_path / "custom.yaml"
        cli_file.write_text("llm:\n  provider: google\n  model: gemini-pro\n")

        config = load_config(cli_path=str(cli_file))
        assert config.llm.provider == "google"
        assert config.llm.model == "gemini-pro"

    def test_user_global_config_used_as_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # No project-local config
        fake_home = tmp_path / "fakehome"
        (fake_home / ".chronicler").mkdir(parents=True)
        user_config = fake_home / ".chronicler" / "config.yaml"
        user_config.write_text("log_level: debug\n")
        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        config = load_config()
        assert config.log_level == "debug"

    def test_env_vars_expanded_in_loaded_config(self, tmp_path, monkeypatch):
        from chronicler_core.config.loader import _ALLOWED_ENV_VARS
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MY_MODEL", "gpt-4-turbo")
        yaml_file = tmp_path / "chronicler.yaml"
        yaml_file.write_text("llm:\n  provider: openai\n  model: ${MY_MODEL}\n")
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")

        with patch("chronicler_core.config.loader._ALLOWED_ENV_VARS", _ALLOWED_ENV_VARS | {"MY_MODEL"}):
            config = load_config()
            assert config.llm.model == "gpt-4-turbo"

    def test_empty_yaml_file_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        yaml_file = tmp_path / "chronicler.yaml"
        yaml_file.write_text("")  # empty
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")

        config = load_config()
        assert config.llm.provider == "anthropic"
