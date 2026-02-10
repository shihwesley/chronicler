"""Tests for the Mercator scanner integration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chronicler_core.config.models import MerkleConfig
from chronicler_core.merkle.scanner import (
    DiffResult,
    MercatorScanner,
    ScanResult,
)


# ── Dataclass basics ─────────────────────────────────────────────────


def test_scan_result_dataclass():
    """ScanResult holds file hashes and optional token counts."""
    sr = ScanResult(
        files={"a.py": "abc123def456", "b.py": "fedcba654321"},
        total_tokens=500,
        merkle_root_hash="aabbccdd1122",
    )
    assert len(sr.files) == 2
    assert sr.total_tokens == 500
    assert sr.merkle_root_hash == "aabbccdd1122"


def test_scan_result_defaults():
    """ScanResult defaults to no tokens and empty root hash."""
    sr = ScanResult(files={})
    assert sr.total_tokens is None
    assert sr.merkle_root_hash == ""


def test_diff_result_dataclass():
    """DiffResult tracks changed/added/removed paths."""
    dr = DiffResult(
        changed=["x.py"],
        added=["y.py"],
        removed=["z.py"],
        has_changes=True,
    )
    assert dr.changed == ["x.py"]
    assert dr.added == ["y.py"]
    assert dr.removed == ["z.py"]
    assert dr.has_changes is True


def test_diff_result_defaults():
    """DiffResult defaults to empty lists and no changes."""
    dr = DiffResult()
    assert dr.changed == []
    assert dr.added == []
    assert dr.removed == []
    assert dr.has_changes is False


# ── Discovery ────────────────────────────────────────────────────────


def test_discover_mercator_from_config_path(tmp_path: Path):
    """When config.mercator_path points to a real file, discovery returns it."""
    script = tmp_path / "scan-codebase.py"
    script.write_text("#!/usr/bin/env python3\nprint('hi')")

    config = MerkleConfig(mercator_path=str(script))
    scanner = MercatorScanner(config)
    found = scanner.discover_mercator()
    assert found == script


def test_discover_mercator_from_env(tmp_path: Path):
    """$CLAUDE_PLUGIN_ROOT is checked for the scanner script."""
    plugin_root = tmp_path / "plugins"
    script_dir = plugin_root / "skills" / "mercator-ai" / "scripts"
    script_dir.mkdir(parents=True)
    script = script_dir / "scan-codebase.py"
    script.write_text("#!/usr/bin/env python3")

    config = MerkleConfig()
    scanner = MercatorScanner(config)

    with patch.dict("os.environ", {"CLAUDE_PLUGIN_ROOT": str(plugin_root)}):
        found = scanner.discover_mercator()
    assert found == script


def test_discover_mercator_not_found():
    """When no Mercator installation exists, discovery returns None."""
    config = MerkleConfig()
    scanner = MercatorScanner(config)

    with patch.dict("os.environ", {}, clear=True):
        # Also ensure the home glob won't match anything real
        with patch("pathlib.Path.home", return_value=Path("/nonexistent/fakehome")):
            found = scanner.discover_mercator()
    assert found is None


def test_discover_mercator_caches_result(tmp_path: Path):
    """Discovery is only performed once; subsequent calls return the cached value."""
    script = tmp_path / "scan-codebase.py"
    script.write_text("#!/usr/bin/env python3")

    config = MerkleConfig(mercator_path=str(script))
    scanner = MercatorScanner(config)

    first = scanner.discover_mercator()
    # Delete the file — cached result should still be returned
    script.unlink()
    second = scanner.discover_mercator()
    assert first == second


# ── Fallback scan ────────────────────────────────────────────────────


def test_fallback_scan(tmp_path: Path):
    """Without Mercator, scan falls back to the built-in walker."""
    (tmp_path / "app.py").write_text("print('hello')")
    (tmp_path / "lib.py").write_text("x = 1")

    config = MerkleConfig()
    scanner = MercatorScanner(config)
    # Force no Mercator
    scanner._searched = True
    scanner._mercator_path = None

    result = scanner.scan(tmp_path)
    assert "app.py" in result.files
    assert "lib.py" in result.files
    assert len(result.files["app.py"]) == 12
    assert result.total_tokens is None


def test_fallback_scan_respects_ignore_patterns(tmp_path: Path):
    """Fallback scanner skips directories in ignore_patterns."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("code")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("module")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("venv stuff")

    config = MerkleConfig()  # default ignore includes node_modules, .venv
    scanner = MercatorScanner(config)
    scanner._searched = True
    scanner._mercator_path = None

    result = scanner.scan(tmp_path)
    assert "src/main.py" in result.files
    assert "node_modules/dep.js" not in result.files
    assert ".venv/lib.py" not in result.files


# ── Mercator scan (mocked subprocess) ────────────────────────────────


def test_mercator_scan_parses_json(tmp_path: Path):
    """When Mercator runs successfully, its JSON output is parsed into ScanResult."""
    mercator_output = json.dumps({
        "files": [
            {"path": "src/app.py", "hash": "aabbccddeeff"},
            {"path": "README.md", "hash": "112233445566"},
        ],
        "total_tokens": 1234,
        "merkle_root_hash": "rootrootroot",
    })

    script = tmp_path / "scan-codebase.py"
    script.write_text("#!/usr/bin/env python3")

    config = MerkleConfig(mercator_path=str(script))
    scanner = MercatorScanner(config)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mercator_output

    with patch("chronicler_core.merkle.scanner.subprocess.run", return_value=mock_result):
        result = scanner.scan(tmp_path)

    assert result.files == {
        "src/app.py": "aabbccddeeff",
        "README.md": "112233445566",
    }
    assert result.total_tokens == 1234
    assert result.merkle_root_hash == "rootrootroot"


def test_mercator_scan_falls_back_on_failure(tmp_path: Path):
    """If Mercator exits non-zero, the fallback scanner is used instead."""
    (tmp_path / "real.py").write_text("content")
    script = tmp_path / "scan-codebase.py"
    script.write_text("#!/usr/bin/env python3")

    config = MerkleConfig(mercator_path=str(script))
    scanner = MercatorScanner(config)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "error"

    with patch("chronicler_core.merkle.scanner.subprocess.run", return_value=mock_result):
        result = scanner.scan(tmp_path)

    # Should have gotten the file via fallback
    assert "real.py" in result.files
    assert result.total_tokens is None


def test_mercator_scan_falls_back_on_timeout(tmp_path: Path):
    """If Mercator times out, the fallback scanner is used."""
    (tmp_path / "real.py").write_text("content")
    script = tmp_path / "scan-codebase.py"
    script.write_text("#!/usr/bin/env python3")

    config = MerkleConfig(mercator_path=str(script))
    scanner = MercatorScanner(config)

    with patch(
        "chronicler_core.merkle.scanner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="uv", timeout=60),
    ):
        result = scanner.scan(tmp_path)

    assert "real.py" in result.files


# ── Fallback diff ────────────────────────────────────────────────────


def test_fallback_diff(tmp_path: Path):
    """Fallback diff compares a fresh scan against a manifest file."""
    (tmp_path / "a.py").write_text("original")
    (tmp_path / "b.py").write_text("new file")

    # Manifest has a.py with a different hash, and c.py that no longer exists
    from chronicler_core.merkle.tree import compute_hash
    manifest = {
        "files": {
            "a.py": "000000000000",  # different from actual hash
            "c.py": "111111111111",  # removed
        }
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    config = MerkleConfig()
    scanner = MercatorScanner(config)
    scanner._searched = True
    scanner._mercator_path = None

    result = scanner.diff(tmp_path, manifest_path)
    assert "a.py" in result.changed
    assert "b.py" in result.added
    assert "c.py" in result.removed
    assert result.has_changes is True
