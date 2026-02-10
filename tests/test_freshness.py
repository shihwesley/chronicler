"""Tests for the freshness subsystem — staleness, watching, regeneration."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chronicler_core.freshness import (
    FreshnessWatcher,
    RegenerationReport,
    StalenessReport,
    check_staleness,
    regenerate_stale,
)
from chronicler_core.merkle.tree import MerkleTree


# ── Helpers ──────────────────────────────────────────────────────────


def _make_project(tmp_path: Path) -> Path:
    """Create a small project with source files and docs."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "util.py").write_text("def helper(): pass")
    (tmp_path / "README.md").write_text("# Project")
    return tmp_path


def _make_project_with_docs(tmp_path: Path) -> Path:
    """Create a project with paired .tech.md docs."""
    root = _make_project(tmp_path)
    doc_dir = root / ".chronicler"
    doc_dir.mkdir()
    # Paired doc for src/main.py (component-id style)
    (doc_dir / "src-main.tech.md").write_text("# main.py docs")
    return root


def _build_and_save_tree(root: Path) -> None:
    """Build a merkle tree and persist it to .chronicler/merkle-tree.json."""
    tree = MerkleTree.build(root)
    out = root / ".chronicler" / "merkle-tree.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tree.save(out)


# ── check_staleness ──────────────────────────────────────────────────


class TestCheckStaleness:
    def test_fresh_project_returns_empty(self, tmp_path: Path):
        """No stale/uncovered/orphaned entries when everything is fresh and covered."""
        root = _make_project_with_docs(tmp_path)
        # Add docs for the other files too
        doc_dir = root / ".chronicler"
        (doc_dir / "src-util.tech.md").write_text("# util docs")
        (doc_dir / "README.tech.md").write_text("# readme docs")

        _build_and_save_tree(root)
        report = check_staleness(root)

        assert report.stale == []
        assert report.total_files > 0

    def test_detects_stale_files(self, tmp_path: Path):
        """Modifying a source file after tree build makes it stale."""
        root = _make_project(tmp_path)
        _build_and_save_tree(root)

        # Modify a file after the tree was saved
        (root / "src" / "main.py").write_text("print('changed')")

        report = check_staleness(root)
        stale_paths = [e.source_path for e in report.stale]
        assert "src/main.py" in stale_paths

        # The hashes should differ
        entry = next(e for e in report.stale if e.source_path == "src/main.py")
        assert entry.current_hash != entry.recorded_hash

    def test_detects_uncovered_files(self, tmp_path: Path):
        """Source files with no paired .tech.md are listed as uncovered."""
        root = _make_project(tmp_path)
        _build_and_save_tree(root)

        report = check_staleness(root)
        # None of the files have docs, so all should be uncovered
        assert "src/main.py" in report.uncovered
        assert "src/util.py" in report.uncovered
        assert "README.md" in report.uncovered

    def test_detects_orphaned_docs(self, tmp_path: Path):
        """A .tech.md with no matching source file is orphaned."""
        root = _make_project_with_docs(tmp_path)
        doc_dir = root / ".chronicler"
        # This doc has no matching source file
        (doc_dir / "deleted-module.tech.md").write_text("# ghost docs")

        _build_and_save_tree(root)
        report = check_staleness(root)

        assert ".chronicler/deleted-module.tech.md" in report.orphaned

    def test_performance_100_files(self, tmp_path: Path):
        """check_staleness runs under 500ms for a 100-file project."""
        root = tmp_path / "bigproject"
        root.mkdir()
        src = root / "src"
        src.mkdir()
        for i in range(100):
            (src / f"mod_{i:03d}.py").write_text(f"# module {i}\nx = {i}")

        _build_and_save_tree(root)

        start = time.monotonic()
        report = check_staleness(root)
        elapsed = time.monotonic() - start

        assert report.total_files == 100
        assert elapsed < 0.5, f"Took {elapsed:.3f}s, expected < 0.5s"


# ── FreshnessWatcher ─────────────────────────────────────────────────


class TestFreshnessWatcher:
    def test_detects_file_changes(self, tmp_path: Path):
        """Writing a file while the watcher is running adds it to stale_paths."""
        root = _make_project(tmp_path)
        watcher = FreshnessWatcher(root, debounce_seconds=0.1)
        watcher.start()

        try:
            # Give the observer a moment to spin up
            time.sleep(0.3)

            # Write a new file
            target = root / "src" / "new_file.py"
            target.write_text("x = 1")

            # Poll until the path appears or we time out (3s)
            deadline = time.monotonic() + 3.0
            found = False
            while time.monotonic() < deadline:
                paths = watcher.stale_paths
                if any("new_file.py" in p for p in paths):
                    found = True
                    break
                time.sleep(0.1)

            assert found, f"new_file.py not detected; stale_paths = {watcher.stale_paths}"
        finally:
            watcher.stop()

    def test_ignores_chronicler_dir(self, tmp_path: Path):
        """Changes inside .chronicler/ are ignored."""
        root = _make_project(tmp_path)
        (root / ".chronicler").mkdir(exist_ok=True)

        watcher = FreshnessWatcher(root, debounce_seconds=0.1)
        watcher.start()

        try:
            time.sleep(0.3)
            (root / ".chronicler" / "internal.json").write_text("{}")
            # Wait a bit, then confirm it was NOT picked up
            time.sleep(0.5)
            assert not any(
                ".chronicler" in p for p in watcher.stale_paths
            ), "Should not track .chronicler/ changes"
        finally:
            watcher.stop()

    def test_callback_fires(self, tmp_path: Path):
        """The optional callback receives (event_type, path) after debounce."""
        root = _make_project(tmp_path)
        events: list[tuple[str, str]] = []

        def on_change(event_type: str, path: str) -> None:
            events.append((event_type, path))

        watcher = FreshnessWatcher(root, debounce_seconds=0.1, callback=on_change)
        watcher.start()

        try:
            time.sleep(0.3)
            (root / "trigger.txt").write_text("fire")

            deadline = time.monotonic() + 3.0
            found = False
            while time.monotonic() < deadline:
                if any("trigger.txt" in ev[1] for ev in events):
                    found = True
                    break
                time.sleep(0.1)

            assert found, f"Callback never fired for trigger.txt; events = {events}"
        finally:
            watcher.stop()


# ── regenerate_stale ─────────────────────────────────────────────────


class TestRegenerateStale:
    def test_no_drafter_returns_skipped(self, tmp_path: Path):
        """Without a drafter, all stale files are reported as skipped."""
        root = _make_project(tmp_path)
        _build_and_save_tree(root)

        # Make a file stale
        (root / "src" / "main.py").write_text("print('changed')")

        result = regenerate_stale(root, drafter=None)
        assert "src/main.py" in result.skipped
        assert result.regenerated == []
        assert result.failed == []

    def test_with_mock_drafter_regenerates(self, tmp_path: Path):
        """A drafter that succeeds moves entries to regenerated, updates hashes."""
        root = _make_project(tmp_path)
        _build_and_save_tree(root)

        # Make a file stale
        (root / "src" / "main.py").write_text("print('v2')")

        drafter = MagicMock()
        drafter.draft_single.return_value = True

        result = regenerate_stale(root, drafter=drafter)
        assert "src/main.py" in result.regenerated
        assert result.skipped == []
        drafter.draft_single.assert_called()

        # Verify the tree was updated — re-checking should show no stale
        report = check_staleness(root)
        stale_paths = [e.source_path for e in report.stale]
        assert "src/main.py" not in stale_paths

    def test_drafter_failure_recorded(self, tmp_path: Path):
        """When the drafter raises, the file goes to failed with the error."""
        root = _make_project(tmp_path)
        _build_and_save_tree(root)
        (root / "src" / "main.py").write_text("print('v3')")

        drafter = MagicMock()
        drafter.draft_single.side_effect = RuntimeError("LLM timeout")

        result = regenerate_stale(root, drafter=drafter)
        assert len(result.failed) == 1
        assert result.failed[0][0] == "src/main.py"
        assert "LLM timeout" in result.failed[0][1]

    def test_nothing_stale_returns_empty(self, tmp_path: Path):
        """When the project is fresh, regeneration returns an empty report."""
        root = _make_project(tmp_path)
        _build_and_save_tree(root)

        result = regenerate_stale(root)
        assert result.regenerated == []
        assert result.failed == []
        assert result.skipped == []
