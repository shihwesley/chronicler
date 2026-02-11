"""Tests for Chronicler hook entry points and skill modules.

Covers:
  - Hook: session_start (staleness summary)
  - Hook: post_write (stale candidate recording)
  - Hook: pre_read_techmd (stale doc warning)
  - Hook: graceful degradation on ImportError
  - Hook: performance (<200ms for non-regen paths)
  - Skill: init (project detection, config gen, hook installation)
  - Skill: status (report formatting)
  - Skill: regenerate (force regen via regenerate_stale)
  - Skill: configure (read/write chronicler.yaml)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """Minimal project layout with a .chronicler dir and chronicler.yaml."""
    chronicler_dir = tmp_path / ".chronicler"
    chronicler_dir.mkdir()
    (tmp_path / "chronicler.yaml").write_text("llm:\n  provider: anthropic\n")
    return tmp_path


@pytest.fixture()
def tool_input_file(tmp_path: Path) -> Path:
    """Path for a TOOL_INPUT_FILE JSON fixture. Not created yet — write in test."""
    return tmp_path / "tool_input.json"


def _make_staleness_report(
    stale=None, uncovered=None, orphaned=None, total_files=5, total_docs=3
):
    """Build a mock StalenessReport without importing pydantic."""
    report = MagicMock()
    report.stale = stale or []
    report.uncovered = uncovered or []
    report.orphaned = orphaned or []
    report.total_files = total_files
    report.total_docs = total_docs
    return report


def _make_stale_entry(source_path, doc_path=None, current="aaa", recorded="bbb"):
    entry = MagicMock()
    entry.source_path = source_path
    entry.doc_path = doc_path
    entry.current_hash = current
    entry.recorded_hash = recorded
    return entry


# ===========================================================================
# HOOK TESTS
# ===========================================================================


class TestSessionStartHook:
    """session_start.py — fast staleness summary."""

    def test_no_chronicler_dir_is_silent(self, tmp_path, capsys):
        """If the project has no .chronicler/ dir, print nothing and return."""
        from chronicler_lite.hooks.session_start import main

        main(str(tmp_path))
        assert capsys.readouterr().out == ""

    def test_all_fresh(self, project, capsys):
        """When nothing is stale, print the 'all fresh' message."""
        report = _make_staleness_report()

        # Patch at the source — session_start does `from chronicler_core.freshness import check_staleness`
        with patch("chronicler_core.freshness.check_staleness", return_value=report):
            from chronicler_lite.hooks.session_start import main
            main(str(project))

        out = capsys.readouterr().out
        assert "all docs fresh" in out
        assert "(3 tracked)" in out

    def test_stale_report(self, project, capsys):
        """When there are stale/uncovered/orphaned entries, print counts."""
        report = _make_staleness_report(
            stale=[_make_stale_entry("src/a.py")],
            uncovered=["src/b.py", "src/c.py"],
            orphaned=["old.tech.md"],
        )

        with patch("chronicler_core.freshness.check_staleness", return_value=report):
            from chronicler_lite.hooks.session_start import main
            main(str(project))

        out = capsys.readouterr().out
        assert "1 stale" in out
        assert "2 uncovered" in out
        assert "1 orphaned docs" in out

    def test_stale_only(self, project, capsys):
        """When only stale (no uncovered/orphaned), only stale count shown."""
        report = _make_staleness_report(stale=[_make_stale_entry("x.py")])

        with patch("chronicler_core.freshness.check_staleness", return_value=report):
            from chronicler_lite.hooks.session_start import main
            main(str(project))

        out = capsys.readouterr().out
        assert "1 stale" in out
        assert "uncovered" not in out
        assert "orphaned" not in out


class TestPostWriteHook:
    """post_write.py — records written paths to .stale-candidates."""

    def test_appends_file_path(self, project, tool_input_file):
        """Normal write: path is appended to .stale-candidates."""
        src = project / "src" / "main.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("print('hi')")

        tool_input_file.write_text(json.dumps({"file_path": str(src)}))

        from chronicler_lite.hooks.post_write import main
        main(str(tool_input_file))

        candidates = project / ".chronicler" / ".stale-candidates"
        assert candidates.exists()
        lines = candidates.read_text().strip().split("\n")
        assert str(src) in lines

    def test_skips_chronicler_internal(self, project, tool_input_file):
        """Writes inside .chronicler/ should be ignored."""
        internal = project / ".chronicler" / "merkle-tree.json"
        tool_input_file.write_text(json.dumps({"file_path": str(internal)}))

        from chronicler_lite.hooks.post_write import main
        main(str(tool_input_file))

        candidates = project / ".chronicler" / ".stale-candidates"
        assert not candidates.exists()

    def test_skips_relative_chronicler_path(self, project, tool_input_file):
        """Relative paths starting with .chronicler/ should also be skipped."""
        tool_input_file.write_text(json.dumps({"file_path": ".chronicler/foo.md"}))

        from chronicler_lite.hooks.post_write import main
        main(str(tool_input_file))

        candidates = project / ".chronicler" / ".stale-candidates"
        assert not candidates.exists()

    def test_missing_file_path_key(self, project, tool_input_file):
        """If the JSON has no file_path key, do nothing."""
        tool_input_file.write_text(json.dumps({"content": "hello"}))

        from chronicler_lite.hooks.post_write import main
        main(str(tool_input_file))

        candidates = project / ".chronicler" / ".stale-candidates"
        assert not candidates.exists()

    def test_nonexistent_input_file(self, tmp_path):
        """If TOOL_INPUT_FILE doesn't exist, exit silently."""
        from chronicler_lite.hooks.post_write import main
        main(str(tmp_path / "does_not_exist.json"))  # should not raise

    def test_multiple_appends(self, project, tool_input_file):
        """Successive writes accumulate in .stale-candidates."""
        for i in range(3):
            src = project / f"file{i}.py"
            src.write_text(f"v{i}")
            tool_input_file.write_text(json.dumps({"file_path": str(src)}))

            from chronicler_lite.hooks.post_write import main
            main(str(tool_input_file))

        candidates = project / ".chronicler" / ".stale-candidates"
        lines = candidates.read_text().strip().split("\n")
        assert len(lines) == 3


class TestPreReadTechmdHook:
    """pre_read_techmd.py — stale doc warning."""

    def test_non_techmd_file_is_noop(self, tool_input_file, capsys):
        """Reading a regular file (not .tech.md) produces no output."""
        tool_input_file.write_text(json.dumps({"file_path": "/tmp/foo.py"}))

        from chronicler_lite.hooks.pre_read_techmd import main
        main(str(tool_input_file))

        assert capsys.readouterr().out == ""

    def test_stale_techmd_prints_warning(self, project, tool_input_file, capsys):
        """Reading a stale .tech.md prints a warning with source path."""
        # Set up a merkle tree with a node whose doc_path points to our target
        doc = project / ".chronicler" / "main.tech.md"
        doc.write_text("# old doc")
        source = project / "main.py"
        source.write_text("print('updated code')")
        (project / "chronicler.yaml").write_text("llm:\n  provider: anthropic\n")

        # Build a fake merkle tree where the source hash is stale
        from chronicler_core.merkle.models import MerkleNode
        from chronicler_core.merkle.tree import MerkleTree, compute_file_hash
        from datetime import datetime, timezone

        actual_hash = compute_file_hash(source)
        # recorded hash is different => stale
        stale_hash = "000000000000"

        tree = MerkleTree(
            root_hash="fake",
            nodes={
                "main.py": MerkleNode(
                    path="main.py",
                    hash=stale_hash,
                    source_hash=stale_hash,
                    doc_path=".chronicler/main.tech.md",
                    doc_hash="abc",
                ),
            },
            last_scan=datetime.now(timezone.utc),
            root_path=str(project),
        )
        tree_path = project / ".chronicler" / "merkle-tree.json"
        tree.save(tree_path)

        tool_input_file.write_text(json.dumps({"file_path": str(doc)}))

        from chronicler_lite.hooks.pre_read_techmd import main
        main(str(tool_input_file))

        out = capsys.readouterr().out
        assert "WARNING" in out
        assert "main.py" in out
        assert "stale" in out.lower()

    def test_fresh_techmd_is_silent(self, project, tool_input_file, capsys):
        """Reading a fresh .tech.md produces no output."""
        source = project / "main.py"
        source.write_text("print('hello')")
        doc = project / ".chronicler" / "main.tech.md"
        doc.write_text("# doc")

        from chronicler_core.merkle.models import MerkleNode
        from chronicler_core.merkle.tree import MerkleTree, compute_file_hash
        from datetime import datetime, timezone

        current_hash = compute_file_hash(source)

        tree = MerkleTree(
            root_hash="fake",
            nodes={
                "main.py": MerkleNode(
                    path="main.py",
                    hash=current_hash,
                    source_hash=current_hash,
                    doc_path=".chronicler/main.tech.md",
                    doc_hash="abc",
                ),
            },
            last_scan=datetime.now(timezone.utc),
            root_path=str(project),
        )
        (project / ".chronicler" / "merkle-tree.json").parent.mkdir(exist_ok=True)
        tree.save(project / ".chronicler" / "merkle-tree.json")

        tool_input_file.write_text(json.dumps({"file_path": str(doc)}))

        from chronicler_lite.hooks.pre_read_techmd import main
        main(str(tool_input_file))

        assert capsys.readouterr().out == ""

    def test_no_merkle_tree_is_silent(self, project, tool_input_file, capsys):
        """If there's no merkle-tree.json, exit silently."""
        doc = project / ".chronicler" / "main.tech.md"
        doc.write_text("# doc")
        tool_input_file.write_text(json.dumps({"file_path": str(doc)}))

        from chronicler_lite.hooks.pre_read_techmd import main
        main(str(tool_input_file))

        assert capsys.readouterr().out == ""


class TestHookGracefulDegradation:
    """Hooks should exit cleanly if chronicler_core is not importable."""

    def test_session_start_import_error_exits_zero(self, project):
        """session_start exits 0 when chronicler_core is missing (REQ-1)."""
        with patch("chronicler_core.freshness.check_staleness", side_effect=ImportError("no module")):
            from chronicler_lite.hooks.session_start import main
            # Should call sys.exit(0) instead of raising
            with pytest.raises(SystemExit) as exc_info:
                main(str(project))
            assert exc_info.value.code == 0

    def test_post_write_no_external_deps(self, project, tool_input_file):
        """post_write uses only stdlib — no chronicler_core import needed."""
        src = project / "src" / "app.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("x = 1")
        tool_input_file.write_text(json.dumps({"file_path": str(src)}))

        # Temporarily block chronicler_core
        with patch.dict("sys.modules", {"chronicler_core": None}):
            from chronicler_lite.hooks.post_write import main
            main(str(tool_input_file))

        candidates = project / ".chronicler" / ".stale-candidates"
        assert candidates.exists()


class TestHookErrorPaths:
    """Hooks must exit 0 on all errors (REQ-1, REQ-2, REQ-5)."""

    def test_post_write_malformed_json_exits_zero(self, tool_input_file, capsys):
        """Malformed JSON in tool input should log warning and return (REQ-5)."""
        tool_input_file.write_text("not valid json{}")

        from chronicler_lite.hooks.post_write import main
        # Should not raise, should log warning
        main(str(tool_input_file))
        # No exception = success

    def test_post_write_io_error_exits_zero(self, project, tool_input_file):
        """I/O errors during candidate file write should exit 0 (REQ-5)."""
        from chronicler_lite.hooks.post_write import main

        # Create a valid input file
        src = project / "test.py"
        src.write_text("x = 1")
        tool_input_file.write_text(json.dumps({"file_path": str(src)}))

        # Patch open() to raise OSError when writing to .stale-candidates
        original_open = open
        def failing_open(path, *args, **kwargs):
            if ".stale-candidates" in str(path):
                raise OSError("disk full")
            return original_open(path, *args, **kwargs)

        with patch("builtins.open", failing_open):
            with pytest.raises(SystemExit) as exc_info:
                main(str(tool_input_file))
            assert exc_info.value.code == 0

    def test_pre_read_techmd_malformed_json_exits_zero(self, tool_input_file):
        """Malformed JSON should log warning and return (REQ-2, REQ-5)."""
        tool_input_file.write_text("{bad json")

        from chronicler_lite.hooks.pre_read_techmd import main
        # Should not raise
        main(str(tool_input_file))

    def test_pre_read_techmd_import_error_exits_zero(self, project, tool_input_file):
        """Import errors should exit 0 (REQ-1, REQ-3)."""
        doc = project / ".chronicler" / "test.tech.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# doc")
        (project / ".chronicler" / "merkle-tree.json").write_text("{}")
        tool_input_file.write_text(json.dumps({"file_path": str(doc)}))

        # Patch MerkleTree.load to raise ImportError
        with patch("chronicler_core.merkle.tree.MerkleTree.load", side_effect=ImportError("no module")):
            from chronicler_lite.hooks.pre_read_techmd import main
            with pytest.raises(SystemExit) as exc_info:
                main(str(tool_input_file))
            assert exc_info.value.code == 0

    def test_pre_read_techmd_merkle_load_error_exits_zero(self, project, tool_input_file):
        """Errors loading merkle tree should exit 0 (REQ-5)."""
        doc = project / ".chronicler" / "test.tech.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# doc")

        # Create corrupted merkle tree file
        tree_file = project / ".chronicler" / "merkle-tree.json"
        tree_file.write_text("corrupted data")

        tool_input_file.write_text(json.dumps({"file_path": str(doc)}))

        from chronicler_lite.hooks.pre_read_techmd import main
        # Should catch the error and exit 0
        with pytest.raises(SystemExit) as exc_info:
            main(str(tool_input_file))
        assert exc_info.value.code == 0

    def test_session_start_freshness_check_error_exits_zero(self, project):
        """Errors in freshness check should exit 0 (REQ-1, REQ-5)."""
        with patch("chronicler_core.freshness.check_staleness", side_effect=RuntimeError("db error")):
            from chronicler_lite.hooks.session_start import main
            with pytest.raises(SystemExit) as exc_info:
                main(str(project))
            assert exc_info.value.code == 0

    def test_session_start_os_error_exits_zero(self, tmp_path):
        """OS errors should exit 0 (REQ-5)."""
        from chronicler_lite.hooks.session_start import main

        # Create .chronicler dir but make it fail during check
        chronicler_dir = tmp_path / ".chronicler"
        chronicler_dir.mkdir()

        with patch("pathlib.Path.resolve", side_effect=OSError("permission denied")):
            with pytest.raises(SystemExit) as exc_info:
                main(str(tmp_path))
            assert exc_info.value.code == 0

    def test_all_hooks_log_warnings_on_error(self, project, tool_input_file, caplog):
        """All hooks should log warnings when they fail (REQ-2)."""
        import logging

        # Test post_write
        from chronicler_lite.hooks.post_write import main as post_write_main

        # Create a valid input but make open() fail
        src = project / "test.py"
        src.write_text("x = 1")
        tool_input_file.write_text(json.dumps({"file_path": str(src)}))

        original_open = open
        def failing_open(path, *args, **kwargs):
            if ".stale-candidates" in str(path):
                raise RuntimeError("test error")
            return original_open(path, *args, **kwargs)

        with caplog.at_level(logging.WARNING):
            with patch("builtins.open", failing_open):
                try:
                    post_write_main(str(tool_input_file))
                except SystemExit:
                    pass

        # Check that warning was logged (actual message is "chronicler post_write hook failed")
        assert any("post_write hook failed" in record.message for record in caplog.records)


class TestHookPerformance:
    """Non-heavy hook paths should complete well under 200ms."""

    def test_session_start_no_chronicler_dir_fast(self, tmp_path):
        """Early-bail path (no .chronicler dir) should be near-instant."""
        from chronicler_lite.hooks.session_start import main
        start = time.perf_counter()
        main(str(tmp_path))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"session_start early bail took {elapsed:.3f}s"

    def test_post_write_fast(self, project, tool_input_file):
        """post_write append path should be well under 200ms."""
        src = project / "fast.py"
        src.write_text("x = 1")
        tool_input_file.write_text(json.dumps({"file_path": str(src)}))

        from chronicler_lite.hooks.post_write import main
        start = time.perf_counter()
        main(str(tool_input_file))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"post_write took {elapsed:.3f}s"

    def test_pre_read_non_techmd_fast(self, tool_input_file):
        """Non-.tech.md reads should bail out almost instantly."""
        tool_input_file.write_text(json.dumps({"file_path": "/some/file.py"}))

        from chronicler_lite.hooks.pre_read_techmd import main
        start = time.perf_counter()
        main(str(tool_input_file))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"pre_read_techmd non-techmd bail took {elapsed:.3f}s"


# ===========================================================================
# SKILL TESTS
# ===========================================================================


class TestSkillInit:
    """skill/init.py — project detection, config gen, hook installation."""

    def test_detect_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[build-system]\n")

        from chronicler_lite.skill.init import detect_project_type
        assert detect_project_type(tmp_path) == "python"

    def test_detect_node_project(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")

        from chronicler_lite.skill.init import detect_project_type
        assert detect_project_type(tmp_path) == "node"

    def test_detect_unknown_project(self, tmp_path):
        from chronicler_lite.skill.init import detect_project_type
        assert detect_project_type(tmp_path) is None

    def test_generate_config_creates_yaml(self, tmp_path, capsys):
        from chronicler_lite.skill.init import generate_config
        path = generate_config(tmp_path)
        assert path.exists()
        assert path.name == "chronicler.yaml"
        content = path.read_text()
        assert "llm:" in content

    def test_generate_config_skips_existing(self, tmp_path, capsys):
        existing = tmp_path / "chronicler.yaml"
        existing.write_text("custom: true\n")

        from chronicler_lite.skill.init import generate_config
        generate_config(tmp_path)

        assert existing.read_text() == "custom: true\n"
        assert "already exists" in capsys.readouterr().out

    def test_full_init_flow(self, tmp_path, capsys):
        """End-to-end init: creates config and merkle tree."""
        (tmp_path / "app.py").write_text("print('hello')")

        from chronicler_lite.skill.init import main
        main(str(tmp_path))

        assert (tmp_path / "chronicler.yaml").exists()
        assert (tmp_path / ".chronicler" / "merkle-tree.json").exists()

        out = capsys.readouterr().out
        assert "Chronicler init" in out
        assert "Done" in out


class TestSkillStatus:
    """skill/status.py — staleness report formatting."""

    def test_status_formats_table(self, capsys):
        report = _make_staleness_report(
            stale=[_make_stale_entry("a.py", doc_path=".chronicler/a.tech.md")],
            uncovered=["b.py"],
            orphaned=["old.tech.md"],
            total_files=10,
            total_docs=5,
        )

        from chronicler_lite.skill import status
        with patch.object(status, "check_staleness", return_value=report):
            status.main("/fake")

        out = capsys.readouterr().out
        assert "Chronicler Status" in out
        assert "Stale" in out
        assert "Uncovered" in out
        assert "Orphaned" in out
        assert "a.py" in out  # stale file listed

    def test_status_clean_project(self, capsys):
        report = _make_staleness_report(total_files=8, total_docs=8)

        from chronicler_lite.skill import status
        with patch.object(status, "check_staleness", return_value=report):
            status.main("/fake")

        out = capsys.readouterr().out
        assert "Fresh" in out
        # No "Stale files:" section when nothing stale
        assert "Stale files:" not in out


class TestSkillRegenerate:
    """skill/regenerate.py — force regeneration."""

    def test_regenerate_all_no_drafter(self, capsys):
        """Without a drafter, all stale files show as skipped."""
        mock_result = MagicMock()
        mock_result.regenerated = []
        mock_result.skipped = ["src/a.py", "src/b.py"]
        mock_result.failed = []

        from chronicler_lite.skill import regenerate
        with patch.object(regenerate, "regenerate_stale", return_value=mock_result):
            regenerate.main()

        out = capsys.readouterr().out
        assert "skipped" in out.lower()
        assert "src/a.py" in out
        assert "src/b.py" in out

    def test_regenerate_all_fresh(self, capsys):
        """When everything is fresh, print a clean message."""
        mock_result = MagicMock()
        mock_result.regenerated = []
        mock_result.skipped = []
        mock_result.failed = []

        from chronicler_lite.skill import regenerate
        with patch.object(regenerate, "regenerate_stale", return_value=mock_result):
            regenerate.main()

        out = capsys.readouterr().out
        assert "fresh" in out.lower()

    def test_regenerate_single_stale(self, capsys):
        """Single-file mode should show hash diff for a stale file."""
        report = _make_staleness_report(
            stale=[_make_stale_entry("src/x.py", doc_path=".chronicler/x.tech.md")],
        )

        from chronicler_lite.skill import regenerate
        with patch.object(regenerate, "check_staleness", return_value=report):
            regenerate.main("src/x.py")

        out = capsys.readouterr().out
        assert "Stale: src/x.py" in out
        assert "Recorded hash" in out
        assert "Current hash" in out

    def test_regenerate_single_fresh(self, capsys):
        """Single-file mode for a fresh file."""
        report = _make_staleness_report(stale=[])

        from chronicler_lite.skill import regenerate
        with patch.object(regenerate, "check_staleness", return_value=report):
            regenerate.main("src/clean.py")

        out = capsys.readouterr().out
        assert "fresh" in out.lower()


class TestSkillConfigure:
    """skill/configure.py — read and update chronicler.yaml."""

    def test_read_config(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "chronicler.yaml").write_text("llm:\n  provider: anthropic\n")

        from chronicler_lite.skill.configure import main
        main([])

        out = capsys.readouterr().out
        assert "anthropic" in out

    def test_set_single_value(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "chronicler.yaml").write_text("llm:\n  provider: anthropic\n")

        from chronicler_lite.skill.configure import main
        main(["llm.provider=openai"])

        data = yaml.safe_load((tmp_path / "chronicler.yaml").read_text())
        assert data["llm"]["provider"] == "openai"

    def test_set_boolean_value(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "chronicler.yaml").write_text("output:\n  create_index: false\n")

        from chronicler_lite.skill.configure import main
        main(["output.create_index=true"])

        data = yaml.safe_load((tmp_path / "chronicler.yaml").read_text())
        assert data["output"]["create_index"] is True

    def test_set_integer_value(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "chronicler.yaml").write_text("llm:\n  max_tokens: 2048\n")

        from chronicler_lite.skill.configure import main
        main(["llm.max_tokens=8192"])

        data = yaml.safe_load((tmp_path / "chronicler.yaml").read_text())
        assert data["llm"]["max_tokens"] == 8192

    def test_no_config_file_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        from chronicler_lite.skill.configure import main
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1

    def test_invalid_arg_format_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "chronicler.yaml").write_text("llm:\n  provider: anthropic\n")

        from chronicler_lite.skill.configure import main
        with pytest.raises(SystemExit) as exc_info:
            main(["bad-argument-no-equals"])
        assert exc_info.value.code == 1

    def test_creates_nested_keys(self, tmp_path, monkeypatch):
        """Setting a deeply nested key that doesn't exist yet should create it."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "chronicler.yaml").write_text("{}\n")

        from chronicler_lite.skill.configure import main
        main(["new.deep.key=hello"])

        data = yaml.safe_load((tmp_path / "chronicler.yaml").read_text())
        assert data["new"]["deep"]["key"] == "hello"
