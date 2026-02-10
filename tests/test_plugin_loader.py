"""Tests for chronicler_core.plugins.loader — discovery, loading, fallback, errors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chronicler_core.config.models import ChroniclerConfig, PluginsConfig
from chronicler_core.interfaces.graph import GraphNode, GraphEdge, GraphPlugin
from chronicler_core.interfaces.queue import Job, QueuePlugin
from chronicler_core.interfaces.rbac import Permission, RBACPlugin
from chronicler_core.interfaces.storage import SearchResult, StoragePlugin
from chronicler_core.plugins.loader import PluginLoader, PluginNotFoundError


# -- Helpers ----------------------------------------------------------------


def make_entry_point(name: str, load_return=None):
    """Build a mock entry point with .name and .load()."""
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = load_return or MagicMock()
    return ep


def make_loader(*, queue=None, graph=None, rbac=None, storage=None) -> PluginLoader:
    """Build a PluginLoader with optional plugin config overrides."""
    plugins = PluginsConfig(queue=queue, graph=graph, rbac=rbac, storage=storage)
    config = ChroniclerConfig(plugins=plugins)
    return PluginLoader(config)


def _ep_side_effect(mapping: dict[str, list]):
    """Return a side_effect function for entry_points(group=...).

    mapping: {"chronicler.plugins.queue": [ep1, ep2], ...}
    Unrecognized groups return [].
    """
    def _side_effect(*, group):
        return mapping.get(group, [])
    return _side_effect


# -- Discovery tests -------------------------------------------------------


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_discover_empty(mock_eps):
    """No registered entry points -> empty lists for every plugin type."""
    mock_eps.side_effect = _ep_side_effect({})
    loader = make_loader()
    result = loader.discover()

    assert set(result.keys()) == {"queue", "graph", "rbac", "storage"}
    for names in result.values():
        assert names == []


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_discover_finds_registered_plugins(mock_eps):
    """Two queue + one graph entry point show up correctly."""
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.queue": [
            make_entry_point("sqs"),
            make_entry_point("pubsub"),
        ],
        "chronicler.plugins.graph": [
            make_entry_point("neo4j"),
        ],
    })
    loader = make_loader()
    result = loader.discover()

    assert result["queue"] == ["sqs", "pubsub"]
    assert result["graph"] == ["neo4j"]
    assert result["rbac"] == []
    assert result["storage"] == []


# -- Loading from entry points ---------------------------------------------


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_queue_from_entry_point(mock_eps):
    """Explicit name loads the matching queue entry point."""
    sentinel = MagicMock(name="FakeQueueClass")
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.queue": [make_entry_point("sqs", sentinel)],
    })
    loader = make_loader()
    assert loader.load_queue(name="sqs") is sentinel


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_graph_from_entry_point(mock_eps):
    """Explicit name loads the matching graph entry point."""
    sentinel = MagicMock(name="FakeGraphClass")
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.graph": [make_entry_point("neo4j", sentinel)],
    })
    loader = make_loader()
    assert loader.load_graph(name="neo4j") is sentinel


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_storage_from_entry_point(mock_eps):
    """Explicit name loads the matching storage entry point."""
    sentinel = MagicMock(name="FakeStorageClass")
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.storage": [make_entry_point("s3", sentinel)],
    })
    loader = make_loader()
    assert loader.load_storage(name="s3") is sentinel


# -- RBAC special handling -------------------------------------------------


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_rbac_returns_none_when_missing(mock_eps):
    """No RBAC entry point and no config -> returns None (not an error)."""
    mock_eps.side_effect = _ep_side_effect({})
    loader = make_loader()
    assert loader.load_rbac() is None


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_rbac_loads_when_registered(mock_eps):
    """RBAC entry point registered -> load_rbac returns the class."""
    sentinel = MagicMock(name="FakeRBACClass")
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.rbac": [make_entry_point("casbin", sentinel)],
    })
    loader = make_loader(rbac="casbin")
    assert loader.load_rbac() is sentinel


# -- Config override -------------------------------------------------------


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_queue_uses_config_name(mock_eps):
    """config.plugins.queue='sqs' causes load_queue() to pick the 'sqs' entry point."""
    sentinel = MagicMock(name="SQSQueue")
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.queue": [
            make_entry_point("pubsub", MagicMock()),
            make_entry_point("sqs", sentinel),
        ],
    })
    loader = make_loader(queue="sqs")
    assert loader.load_queue() is sentinel


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_explicit_name_overrides_config(mock_eps):
    """Explicit name='pubsub' wins over config.plugins.queue='sqs'."""
    sqs_cls = MagicMock(name="SQSQueue")
    pubsub_cls = MagicMock(name="PubSubQueue")
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.queue": [
            make_entry_point("sqs", sqs_cls),
            make_entry_point("pubsub", pubsub_cls),
        ],
    })
    loader = make_loader(queue="sqs")
    # Explicit name should override the config value
    assert loader.load_queue(name="pubsub") is pubsub_cls


# -- Lite fallback ---------------------------------------------------------


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_fallback_to_lite_sqlite_queue(mock_eps):
    """No entry points + no config -> tries chronicler_lite.queue.sqlite_queue import."""
    mock_eps.side_effect = _ep_side_effect({})
    fake_class = MagicMock(name="SQLiteQueue")
    fake_module = MagicMock()
    fake_module.SQLiteQueue = fake_class

    with patch("builtins.__import__", return_value=fake_module) as mock_import:
        loader = make_loader()
        result = loader.load_queue()

    assert result is fake_class
    mock_import.assert_called_with(
        "chronicler_lite.queue.sqlite_queue", fromlist=["SQLiteQueue"]
    )


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_fallback_to_lite_memvid_storage(mock_eps):
    """No entry points + no config -> tries chronicler_lite.storage.memvid_storage import."""
    mock_eps.side_effect = _ep_side_effect({})
    fake_class = MagicMock(name="MemVidStorage")
    fake_module = MagicMock()
    fake_module.MemVidStorage = fake_class

    with patch("builtins.__import__", return_value=fake_module) as mock_import:
        loader = make_loader()
        result = loader.load_storage()

    assert result is fake_class
    mock_import.assert_called_with(
        "chronicler_lite.storage.memvid_storage", fromlist=["MemVidStorage"]
    )


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_no_fallback_for_graph(mock_eps):
    """Graph has no Lite default -> PluginNotFoundError when nothing is registered."""
    mock_eps.side_effect = _ep_side_effect({})
    loader = make_loader()

    with pytest.raises(PluginNotFoundError) as exc_info:
        loader.load_graph()

    assert exc_info.value.plugin_type == "graph"


# -- Error handling --------------------------------------------------------


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_load_unknown_plugin_raises(mock_eps):
    """Explicit name that doesn't match any entry point -> PluginNotFoundError."""
    mock_eps.side_effect = _ep_side_effect({})
    loader = make_loader()

    with pytest.raises(PluginNotFoundError):
        loader.load_queue(name="nonexistent")


def test_plugin_not_found_error_attributes():
    """PluginNotFoundError stores plugin_type and name."""
    err = PluginNotFoundError("queue", "sqs")
    assert err.plugin_type == "queue"
    assert err.name == "sqs"


def test_plugin_not_found_error_message_with_name():
    """Error message includes the requested name."""
    err = PluginNotFoundError("graph", "neo4j")
    assert "graph" in str(err)
    assert "neo4j" in str(err)


def test_plugin_not_found_error_message_without_name():
    """Error message is generic when no name is given."""
    err = PluginNotFoundError("storage")
    assert "storage" in str(err)
    assert "'" not in str(err)  # no quoted name


# -- Protocol compliance ---------------------------------------------------

# Minimal conforming classes for each protocol

class _FakeQueue:
    def enqueue(self, job): return job.id
    def dequeue(self): return None
    def ack(self, job_id): pass
    def nack(self, job_id, reason): pass
    def dead_letters(self): return []


class _FakeGraph:
    def add_node(self, node): pass
    def add_edge(self, edge): pass
    def neighbors(self, node_id, depth=1): return []
    def query(self, expression): return []


class _FakeStorage:
    def store(self, doc_id, content, metadata): pass
    def search(self, query, k=10, mode="auto"): return []
    def get(self, doc_id): return None
    def state(self, entity): return {}


class _FakeRBAC:
    def check(self, user_id, permission): return True
    def grant(self, user_id, permission): pass
    def revoke(self, user_id, permission): pass
    def list_permissions(self, user_id): return []


@patch("chronicler_core.plugins.loader.importlib.metadata.entry_points")
def test_loaded_plugin_matches_protocol(mock_eps):
    """Plugin classes loaded via entry points satisfy their runtime_checkable Protocol."""
    mock_eps.side_effect = _ep_side_effect({
        "chronicler.plugins.queue": [make_entry_point("q", _FakeQueue)],
        "chronicler.plugins.graph": [make_entry_point("g", _FakeGraph)],
        "chronicler.plugins.storage": [make_entry_point("s", _FakeStorage)],
        "chronicler.plugins.rbac": [make_entry_point("r", _FakeRBAC)],
    })
    loader = make_loader(queue="q", graph="g", storage="s", rbac="r")

    assert isinstance(loader.load_queue()(), QueuePlugin)
    assert isinstance(loader.load_graph()(), GraphPlugin)
    assert isinstance(loader.load_storage()(), StoragePlugin)
    assert isinstance(loader.load_rbac()(), RBACPlugin)
