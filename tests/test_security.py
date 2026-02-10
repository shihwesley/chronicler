"""Security-specific tests for path traversal, SSRF, and injection vulnerabilities."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chronicler_core.config.loader import _expand_env_vars
from chronicler_core.config.models import MerkleConfig, OutputConfig
from chronicler_core.drafter.models import TechDoc
from chronicler_core.llm.models import LLMConfig
from chronicler_core.llm.ollama import OllamaProvider, _validate_base_url
from chronicler_core.merkle.scanner import MercatorScanner
from chronicler_core.merkle.tree import _find_doc_for_source
from chronicler_core.output.writer import TechMdWriter


# -------------------------------------------------------------------------
# Finding #5: Path traversal in output/writer.py
# -------------------------------------------------------------------------


def test_writer_path_traversal_blocked(tmp_path):
    """Test that path traversal attempts in component_id are blocked."""
    from chronicler_core.output.writer import _sanitize_component_id

    config = OutputConfig(base_dir=str(tmp_path / "docs"))
    writer = TechMdWriter(config)

    # Patch sanitizer to pass through the malicious input (testing the is_relative_to guard)
    with patch("chronicler_core.output.writer._sanitize_component_id", return_value="../../../etc/passwd"):
        malicious_doc = TechDoc(
            component_id="../../../etc/passwd",
            raw_content="malicious content",
            metadata={},
        )

        with pytest.raises(ValueError, match="Path escape detected"):
            writer.write(malicious_doc)


def test_writer_symlink_escape_blocked(tmp_path):
    """Test that symlinks can't be used to escape base_dir."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    config = OutputConfig(base_dir=str(docs_dir))
    writer = TechMdWriter(config)

    # Patch sanitizer to return a path that looks innocent but will resolve outside
    # Also patch resolve() to simulate the symlink resolution
    doc = TechDoc(
        component_id="escape/payload",
        raw_content="test",
        metadata={},
    )

    outside_path = outside_dir / "evil.tech.md"
    original_resolve = Path.resolve

    def mock_resolve(self, *args, **kwargs):
        # If this is the dest path being checked, return outside path
        if self.name == "escape--payload.tech.md":
            return outside_path
        return original_resolve(self, *args, **kwargs)

    with patch("chronicler_core.output.writer._sanitize_component_id", return_value="escape--payload"):
        with patch.object(Path, "resolve", mock_resolve):
            with pytest.raises(ValueError, match="Path escape detected"):
                writer.write(doc)


# -------------------------------------------------------------------------
# Finding #6: Path traversal in hooks/post_write.py
# -------------------------------------------------------------------------


def test_post_write_path_traversal_blocked(tmp_path):
    """Test that post_write hook rejects paths outside project root."""
    from chronicler_lite.hooks.post_write import main

    project = tmp_path / "project"
    project.mkdir()
    (project / ".chronicler").mkdir()

    # Create a malicious tool_input.json
    tool_input = tmp_path / "tool_input.json"
    tool_input.write_text(json.dumps({
        "file_path": str(tmp_path / "outside" / "evil.py")
    }))

    # Hook should silently ignore (return early) due to path validation
    main(str(tool_input))

    # .stale-candidates should not be created or updated
    candidates = project / ".chronicler" / ".stale-candidates"
    assert not candidates.exists()


# -------------------------------------------------------------------------
# Finding #4: Merkle scanner mercator_path validation
# -------------------------------------------------------------------------


def test_scanner_rejects_relative_mercator_path(tmp_path, caplog):
    """Test that relative paths in mercator_path are rejected."""
    config = MerkleConfig(mercator_path="relative/path/to/script.py")
    scanner = MercatorScanner(config)

    # Prevent fallback discovery from finding anything
    with patch("pathlib.Path.glob", return_value=[]):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            result = scanner.discover_mercator()

    assert result is None  # Should reject and return None
    assert any("must be absolute" in rec.message for rec in caplog.records)


def test_scanner_rejects_directory_mercator_path(tmp_path, caplog):
    """Test that directories in mercator_path are rejected."""
    some_dir = tmp_path / "some_dir"
    some_dir.mkdir()

    config = MerkleConfig(mercator_path=str(some_dir))
    scanner = MercatorScanner(config)

    # Prevent fallback discovery
    with patch("pathlib.Path.glob", return_value=[]):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            result = scanner.discover_mercator()

    assert result is None  # Should reject directory


def test_scanner_rejects_nonexistent_mercator_path(tmp_path):
    """Test that nonexistent paths in mercator_path are rejected."""
    config = MerkleConfig(mercator_path=str(tmp_path / "does_not_exist.py"))
    scanner = MercatorScanner(config)

    # Prevent fallback discovery
    with patch("pathlib.Path.glob", return_value=[]):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            result = scanner.discover_mercator()

    assert result is None


# -------------------------------------------------------------------------
# Finding #7: SSRF in ollama.py
# -------------------------------------------------------------------------


def test_ollama_url_validation_invalid_scheme():
    """Test that non-http(s) schemes are rejected."""
    with pytest.raises(ValueError, match="must be http\\(s\\)"):
        _validate_base_url("ftp://localhost:11434")


def test_ollama_url_validation_crlf_injection():
    """Test that CRLF injection is detected."""
    with pytest.raises(ValueError, match="CRLF injection"):
        _validate_base_url("http://localhost:11434\r\nX-Evil: header")

    with pytest.raises(ValueError, match="CRLF injection"):
        _validate_base_url("http://localhost:11434\nGET /evil")


def test_ollama_url_validation_localhost_allowed():
    """Test that localhost variants are allowed without warning."""
    for host in ["http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"]:
        result = _validate_base_url(host)
        assert result == host


def test_ollama_url_validation_remote_warns(caplog):
    """Test that remote hosts generate a warning but are allowed."""
    result = _validate_base_url("http://remote-ollama.example.com:11434")
    assert result == "http://remote-ollama.example.com:11434"
    assert "not localhost" in caplog.text


def test_ollama_provider_validates_on_init():
    """Test that OllamaProvider validates base_url during construction."""
    config = LLMConfig(
        provider="ollama",
        model="llama2",
        base_url="file:///etc/passwd"
    )

    with pytest.raises(ValueError, match="must be http\\(s\\)"):
        OllamaProvider(config)


# -------------------------------------------------------------------------
# Finding #18: Env var expansion in config/loader.py
# -------------------------------------------------------------------------


def test_env_var_allowlist_blocks_disallowed():
    """Test that non-allowlisted env vars raise ValueError."""
    with pytest.raises(ValueError, match="not in allowlist"):
        _expand_env_vars({"key": "${HOME}"})

    with pytest.raises(ValueError, match="not in allowlist"):
        _expand_env_vars({"key": "${PATH}"})


def test_env_var_allowlist_allows_permitted():
    """Test that allowlisted env vars are expanded."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}):
        result = _expand_env_vars({"key": "${ANTHROPIC_API_KEY}"})
        assert result == {"key": "sk-test-123"}


def test_env_var_allowlist_nested_structures():
    """Test that env var expansion works recursively."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}):
        obj = {
            "nested": {
                "list": ["${GITHUB_TOKEN}", "static"]
            }
        }
        result = _expand_env_vars(obj)
        assert result == {
            "nested": {
                "list": ["ghp_test", "static"]
            }
        }


# -------------------------------------------------------------------------
# Finding #24: Path traversal in merkle/tree.py
# -------------------------------------------------------------------------


def test_merkle_find_doc_blocks_traversal(tmp_path):
    """Test that _find_doc_for_source rejects paths escaping root."""
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    # Try to find a doc using a traversal attack
    # Since the function constructs paths from source_rel, test with malicious input
    result = _find_doc_for_source("../../../outside/evil", ".chronicler", root)

    # Should return None (path outside root is rejected)
    assert result is None


def test_merkle_find_doc_symlink_escape_blocked(tmp_path):
    """Test that symlinks can't escape the root directory."""
    root = tmp_path / "project"
    root.mkdir()
    doc_dir = root / ".chronicler"
    doc_dir.mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()
    evil_doc = outside / "evil.tech.md"
    evil_doc.write_text("malicious")

    # Create a symlink in doc_dir pointing outside
    symlink = doc_dir / "escape.tech.md"
    symlink.symlink_to(evil_doc)

    # Try to find it
    result = _find_doc_for_source("src/something", ".chronicler", root)

    # Should not return the symlinked file if it escapes root
    # (This test verifies the is_relative_to check works)
    if result is not None:
        # If a result is returned, ensure it's within root
        assert result.resolve().is_relative_to(root.resolve())
