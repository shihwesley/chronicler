"""Tests for the Lite CLI commands (search, deps, rebuild, queue status/run)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# ---------------------------------------------------------------------------
# Mock the memvid SDK before importing CLI (same pattern as test_memvid_storage)
# ---------------------------------------------------------------------------

_mock_memvid_module = ModuleType("memvid")
_mock_memvid_cls = MagicMock(name="Memvid")
_mock_memvid_module.Memvid = _mock_memvid_cls  # type: ignore[attr-defined]
sys.modules.setdefault("memvid", _mock_memvid_module)

from chronicler.cli import app  # noqa: E402

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_memvid_mock():
    _mock_memvid_cls.reset_mock()
    yield


@pytest.fixture()
def mock_storage():
    """Patch MemVidStorage at the CLI import site and return the mock instance."""
    instance = MagicMock(name="MemVidStorage_instance")
    with patch(
        "chronicler_lite.storage.memvid_storage.MemVidStorage",
        return_value=instance,
    ) as cls_mock:
        yield instance


@pytest.fixture()
def mock_queue():
    """Patch SQLiteQueue at the CLI import site and return the mock instance."""
    instance = MagicMock(name="SQLiteQueue_instance")
    with patch(
        "chronicler_lite.queue.sqlite_queue.SQLiteQueue",
        return_value=instance,
    ) as cls_mock:
        yield instance


# ---------------------------------------------------------------------------
# chronicler search
# ---------------------------------------------------------------------------


class TestSearchCommand:
    def test_search_shows_results_table(self, mock_storage):
        from chronicler_core.interfaces.storage import SearchResult

        mock_storage.search.return_value = [
            SearchResult(doc_id="auth-svc", content="Auth service handles login.", score=0.92, metadata={}),
            SearchResult(doc_id="api-gw", content="API gateway routes traffic.", score=0.71, metadata={}),
        ]

        result = runner.invoke(app, ["search", "auth", "--mv2-path", "/tmp/fake.mv2"])

        assert result.exit_code == 0
        assert "auth-svc" in result.output
        assert "api-gw" in result.output
        assert "0.9200" in result.output
        mock_storage.search.assert_called_once_with("auth", k=10, mode="auto")

    def test_search_custom_k_and_mode(self, mock_storage):
        from chronicler_core.interfaces.storage import SearchResult

        mock_storage.search.return_value = [
            SearchResult(doc_id="d1", content="x", score=1.0, metadata={}),
        ]

        result = runner.invoke(app, ["search", "test", "--k", "3", "--mode", "lex", "--mv2-path", "/tmp/f.mv2"])

        assert result.exit_code == 0
        mock_storage.search.assert_called_once_with("test", k=3, mode="lex")

    def test_search_no_results(self, mock_storage):
        mock_storage.search.return_value = []

        result = runner.invoke(app, ["search", "nothing", "--mv2-path", "/tmp/f.mv2"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_search_truncates_long_snippet(self, mock_storage):
        from chronicler_core.interfaces.storage import SearchResult

        long_content = "A" * 200
        mock_storage.search.return_value = [
            SearchResult(doc_id="long", content=long_content, score=0.5, metadata={}),
        ]

        result = runner.invoke(app, ["search", "q", "--mv2-path", "/tmp/f.mv2"])

        assert result.exit_code == 0
        # Rich may render the truncation as Unicode ellipsis or the literal "..."
        assert "..." in result.output or "\u2026" in result.output

    def test_search_invalid_mode(self, mock_storage):
        result = runner.invoke(app, ["search", "q", "--mode", "bad", "--mv2-path", "/tmp/f.mv2"])

        assert result.exit_code == 1
        assert "Invalid mode" in result.output


# ---------------------------------------------------------------------------
# chronicler deps
# ---------------------------------------------------------------------------


class TestDepsCommand:
    def test_deps_shows_state_table(self, mock_storage):
        mock_storage.state.return_value = {
            "depends_on": "postgres",
            "exposes": "REST /api/v1",
        }

        result = runner.invoke(app, ["deps", "auth-svc", "--mv2-path", "/tmp/f.mv2"])

        assert result.exit_code == 0
        assert "depends_on" in result.output
        assert "postgres" in result.output
        assert "exposes" in result.output
        mock_storage.state.assert_called_once_with("auth-svc")

    def test_deps_empty_state(self, mock_storage):
        mock_storage.state.return_value = {}

        result = runner.invoke(app, ["deps", "unknown", "--mv2-path", "/tmp/f.mv2"])

        assert result.exit_code == 0
        assert "No state found" in result.output


# ---------------------------------------------------------------------------
# chronicler rebuild
# ---------------------------------------------------------------------------


class TestRebuildCommand:
    def test_rebuild_reports_file_count(self, tmp_path, mock_storage):
        md_dir = tmp_path / ".chronicler"
        md_dir.mkdir()
        (md_dir / "auth.tech.md").write_text("---\ntitle: auth\n---\nAuth docs.")
        (md_dir / "api.tech.md").write_text("API docs.")

        result = runner.invoke(app, [
            "rebuild",
            "--tech-md-dir", str(md_dir),
            "--mv2-path", str(tmp_path / "out.mv2"),
        ])

        assert result.exit_code == 0
        assert "2 .tech.md file(s)" in result.output
        mock_storage.rebuild.assert_called_once_with(str(md_dir))

    def test_rebuild_no_files(self, tmp_path, mock_storage):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(app, [
            "rebuild",
            "--tech-md-dir", str(empty_dir),
            "--mv2-path", str(tmp_path / "out.mv2"),
        ])

        assert result.exit_code == 0
        assert "No .tech.md files" in result.output
        mock_storage.rebuild.assert_not_called()


# ---------------------------------------------------------------------------
# chronicler queue status
# ---------------------------------------------------------------------------


class TestQueueStatusCommand:
    def test_queue_status_shows_stats(self, mock_queue):
        mock_queue.stats.return_value = {
            "pending": 5,
            "processing": 1,
            "completed": 20,
            "failed": 0,
            "dead": 2,
        }

        result = runner.invoke(app, ["queue", "status", "--db-path", "/tmp/q.db"])

        assert result.exit_code == 0
        assert "pending" in result.output
        assert "5" in result.output
        assert "completed" in result.output
        assert "20" in result.output


# ---------------------------------------------------------------------------
# chronicler queue run
# ---------------------------------------------------------------------------


class TestQueueRunCommand:
    def test_queue_run_processes_jobs(self, mock_queue):
        from chronicler_core.interfaces.queue import Job, JobStatus

        job1 = Job(id="j1", payload={"repo": "acme/foo"}, status=JobStatus.processing)
        job2 = Job(id="j2", payload={"repo": "acme/bar"}, status=JobStatus.processing)

        # dequeue returns two jobs then None
        mock_queue.dequeue.side_effect = [job1, job2, None]

        result = runner.invoke(app, ["queue", "run", "--db-path", "/tmp/q.db"])

        assert result.exit_code == 0
        assert "Processed 2 job(s)" in result.output
        assert mock_queue.ack.call_count == 2
        mock_queue.ack.assert_any_call("j1")
        mock_queue.ack.assert_any_call("j2")

    def test_queue_run_empty_queue(self, mock_queue):
        mock_queue.dequeue.return_value = None

        result = runner.invoke(app, ["queue", "run", "--db-path", "/tmp/q.db"])

        assert result.exit_code == 0
        assert "Processed 0 job(s)" in result.output

    def test_queue_run_nacks_on_error(self, mock_queue):
        from chronicler_core.interfaces.queue import Job, JobStatus

        job = Job(id="j-bad", payload={"repo": "acme/broken"}, status=JobStatus.processing)
        mock_queue.dequeue.side_effect = [job, None]
        # ack raises, simulating a processing error that our stub wouldn't hit
        # but we test the nack path by having json.dumps fail on a bad payload
        # Actually, the stub just logs — let's make ack itself raise
        mock_queue.ack.side_effect = RuntimeError("db locked")

        result = runner.invoke(app, ["queue", "run", "--db-path", "/tmp/q.db"])

        assert result.exit_code == 0
        assert "Error processing j-bad" in result.output
        mock_queue.nack.assert_called_once_with("j-bad", "db locked")
        assert "Processed 0 job(s)" in result.output
