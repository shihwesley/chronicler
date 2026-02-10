"""Tests for chronicler_lite.storage.memvid_storage — mocked MemVid SDK."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock the memvid SDK before importing our code so we don't need the real
# package installed.
# ---------------------------------------------------------------------------

_mock_memvid_module = ModuleType("memvid")
_mock_memvid_cls = MagicMock(name="Memvid")
_mock_memvid_module.Memvid = _mock_memvid_cls  # type: ignore[attr-defined]
sys.modules["memvid"] = _mock_memvid_module

from chronicler_core.interfaces.storage import SearchResult, StoragePlugin  # noqa: E402
from chronicler_lite.storage.memvid_storage import MemVidStorage, _split_frontmatter  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_mock():
    """Reset the shared mock before every test."""
    _mock_memvid_cls.reset_mock()
    yield


@pytest.fixture()
def mem_instance() -> MagicMock:
    """A fresh MagicMock representing a Memvid instance."""
    return MagicMock(name="mem_instance")


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_new_mv2_when_path_missing(self, tmp_path: Path, mem_instance: MagicMock):
        mv2 = tmp_path / "data" / "store.mv2"
        assert not mv2.exists()

        _mock_memvid_cls.create.return_value = mem_instance

        storage = MemVidStorage(path=str(mv2))

        _mock_memvid_cls.create.assert_called_once_with(
            path=str(mv2), kind="basic"
        )
        # Parent directory should have been created
        assert mv2.parent.exists()
        assert storage._mem is mem_instance

    def test_opens_existing_mv2(self, tmp_path: Path, mem_instance: MagicMock):
        mv2 = tmp_path / "existing.mv2"
        mv2.touch()

        _mock_memvid_cls.use.return_value = mem_instance

        storage = MemVidStorage(path=str(mv2))

        _mock_memvid_cls.use.assert_called_once_with(
            kind="basic", path=str(mv2)
        )
        assert storage._mem is mem_instance


# ---------------------------------------------------------------------------
# store() tests
# ---------------------------------------------------------------------------


class TestStore:
    def test_calls_put_and_commit(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mv2 = tmp_path / "s.mv2"

        storage = MemVidStorage(path=str(mv2))
        storage.store("doc-1", "some content", {"tag": "api"})

        mem_instance.put.assert_called_once_with(
            text="some content",
            title="doc-1",
            label="tech.md",
            metadata={"tag": "api"},
        )
        mem_instance.commit.assert_called_once()


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------


class TestSearch:
    def test_converts_results_to_search_result(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.find.return_value = [
            {"title": "d1", "text": "hello", "score": 0.9, "metadata": {"a": 1}},
            {"title": "d2", "text": "world", "score": 0.7, "metadata": {}},
        ]

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        results = storage.search("hello world", k=5, mode="vec")

        mem_instance.find.assert_called_once_with("hello world", k=5, mode="vec")
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].doc_id == "d1"
        assert results[0].content == "hello"
        assert results[0].score == 0.9
        assert results[0].metadata == {"a": 1}
        assert results[1].doc_id == "d2"

    def test_empty_results(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.find.return_value = []

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        results = storage.search("nothing")

        assert results == []

    def test_defaults(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.find.return_value = []

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        storage.search("q")

        mem_instance.find.assert_called_once_with("q", k=10, mode="auto")


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------


class TestGet:
    def test_returns_content_on_match(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.find.return_value = [
            {"title": "doc-x", "text": "the content", "score": 1.0}
        ]

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        result = storage.get("doc-x")

        mem_instance.find.assert_called_once_with("doc-x", k=1, mode="lex")
        assert result == "the content"

    def test_returns_none_when_empty(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.find.return_value = []

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        assert storage.get("missing") is None

    def test_returns_none_when_title_mismatch(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.find.return_value = [
            {"title": "other-doc", "text": "wrong", "score": 0.5}
        ]

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        assert storage.get("doc-x") is None


# ---------------------------------------------------------------------------
# state() tests
# ---------------------------------------------------------------------------


class TestState:
    def test_delegates_to_memvid(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance
        mem_instance.state.return_value = {"role": "auth-service", "lang": "python"}

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        result = storage.state("auth-service")

        mem_instance.state.assert_called_once_with("auth-service")
        assert result == {"role": "auth-service", "lang": "python"}


# ---------------------------------------------------------------------------
# enrich_from_frontmatter() tests
# ---------------------------------------------------------------------------


class TestEnrichFromFrontmatter:
    def test_creates_memory_cards(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        edges = [
            {"entity": "auth", "slot": "depends_on", "value": "db"},
            {"entity": "auth", "slot": "exposes", "value": "login_endpoint"},
        ]
        storage.enrich_from_frontmatter("auth-service", edges)

        mem_instance.add_memory_cards.assert_called_once_with([
            {"entity": "auth", "slot": "depends_on", "value": "db"},
            {"entity": "auth", "slot": "exposes", "value": "login_endpoint"},
        ])
        mem_instance.commit.assert_called()

    def test_uses_doc_id_as_fallback_entity(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        edges = [{"slot": "uses", "value": "redis"}]
        storage.enrich_from_frontmatter("my-svc", edges)

        mem_instance.add_memory_cards.assert_called_once_with([
            {"entity": "my-svc", "slot": "uses", "value": "redis"},
        ])

    def test_no_op_when_empty(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        storage.enrich_from_frontmatter("svc", [])

        mem_instance.add_memory_cards.assert_not_called()


# ---------------------------------------------------------------------------
# rebuild() tests
# ---------------------------------------------------------------------------


class TestRebuild:
    def test_reads_tech_md_files(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance

        # Create two .tech.md files
        md_dir = tmp_path / "docs"
        md_dir.mkdir()

        (md_dir / "auth.tech.md").write_text(
            "---\ntitle: auth\nedges:\n  - entity: auth\n    slot: depends_on\n    value: db\n---\nAuth service docs.",
            encoding="utf-8",
        )
        (md_dir / "api.tech.md").write_text(
            "API gateway docs without frontmatter.",
            encoding="utf-8",
        )

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        storage.rebuild(str(md_dir))

        # Both files should have been stored (alphabetical order: api, auth)
        assert mem_instance.put.call_count == 2
        assert mem_instance.commit.call_count >= 2

        # The auth file should also trigger enrich_from_frontmatter
        mem_instance.add_memory_cards.assert_called_once_with([
            {"entity": "auth", "slot": "depends_on", "value": "db"},
        ])


# ---------------------------------------------------------------------------
# _split_frontmatter() helper
# ---------------------------------------------------------------------------


class TestSplitFrontmatter:
    def test_with_frontmatter(self):
        text = "---\ntitle: hello\n---\nBody text."
        fm, body = _split_frontmatter(text)
        assert fm == {"title": "hello"}
        assert body == "Body text."

    def test_without_frontmatter(self):
        text = "Just some text."
        fm, body = _split_frontmatter(text)
        assert fm == {}
        assert body == "Just some text."

    def test_invalid_yaml(self):
        text = "---\n: [invalid\n---\nBody."
        fm, body = _split_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_non_dict_yaml(self):
        text = "---\n- item1\n- item2\n---\nBody."
        fm, body = _split_frontmatter(text)
        assert fm == {}
        assert body == text


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_satisfies_storage_plugin(self, tmp_path: Path, mem_instance: MagicMock):
        _mock_memvid_cls.create.return_value = mem_instance

        storage = MemVidStorage(path=str(tmp_path / "s.mv2"))
        assert isinstance(storage, StoragePlugin)
