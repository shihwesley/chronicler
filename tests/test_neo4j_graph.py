"""Tests for Neo4jGraph plugin and GraphQL schema."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, call, patch

import pytest

from chronicler_core.interfaces.graph import GraphEdge, GraphNode, GraphPlugin


def _has_strawberry() -> bool:
    try:
        import strawberry  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Helpers — fake neo4j module so we never need the real driver
# ---------------------------------------------------------------------------

def _make_mock_neo4j():
    """Return a fake ``neo4j`` module with a mock GraphDatabase."""
    mod = types.ModuleType("neo4j")
    mod.GraphDatabase = MagicMock()
    return mod


@pytest.fixture()
def mock_neo4j():
    mod = _make_mock_neo4j()
    with patch.dict(sys.modules, {"neo4j": mod}):
        yield mod


@pytest.fixture()
def graph(mock_neo4j):
    from chronicler_enterprise.plugins.mnemon.neo4j_graph import Neo4jGraph

    g = Neo4jGraph(uri="bolt://localhost:7687", auth=("neo4j", "test"))
    return g


# ---------------------------------------------------------------------------
# Neo4jGraph unit tests
# ---------------------------------------------------------------------------


def test_add_node_runs_merge_query(graph):
    node = GraphNode(id="n1", type="service", label="Auth")
    graph.add_node(node)

    session = graph._driver.session.return_value.__enter__.return_value
    cypher = session.run.call_args[0][0]
    assert "MERGE" in cypher
    assert "Component" in cypher


def test_add_edge_runs_match_merge(graph):
    edge = GraphEdge(source="a", target="b", relation="depends_on")
    graph.add_edge(edge)

    session = graph._driver.session.return_value.__enter__.return_value
    cypher = session.run.call_args[0][0]
    assert "MATCH" in cypher
    assert "MERGE" in cypher
    assert "RELATES" in cypher


def test_neighbors_returns_graph_nodes(graph):
    # Prepare mock result rows
    mock_record = {"m": {"id": "x1", "type": "entity", "label": "X"}}
    session = graph._driver.session.return_value.__enter__.return_value
    session.run.return_value = [mock_record]

    nodes = graph.neighbors("root")
    assert len(nodes) == 1
    assert isinstance(nodes[0], GraphNode)
    assert nodes[0].id == "x1"


def test_neighbors_respects_depth(graph):
    session = graph._driver.session.return_value.__enter__.return_value
    session.run.return_value = []

    graph.neighbors("root", depth=2)
    cypher = session.run.call_args[0][0]
    assert "[*1..2]" in cypher


def test_query_passthrough(graph):
    session = graph._driver.session.return_value.__enter__.return_value
    fake_record = MagicMock()
    fake_record.__iter__ = MagicMock(return_value=iter([("a", 1)]))
    fake_record.keys = MagicMock(return_value=["a"])
    # dict(record) needs to work — use a real dict wrapped in a list
    session.run.return_value = [{"col": "val"}]

    result = graph.query("RETURN 1")
    session.run.assert_called_once_with("RETURN 1", parameters={})
    assert result == [{"col": "val"}]


def test_sync_from_memvid_creates_nodes_and_edges(graph):
    storage = MagicMock()
    storage.state.return_value = {
        "cards": [
            {"subject": "AuthService", "predicate": "calls", "object": "UserDB"},
        ],
    }

    with patch.object(graph, "add_node") as mock_add_node, \
         patch.object(graph, "add_edge") as mock_add_edge:
        graph.sync_from_memvid(storage)

    assert mock_add_node.call_count == 2
    assert mock_add_edge.call_count == 1

    # Check the subject node
    subj_node = mock_add_node.call_args_list[0][0][0]
    assert subj_node.id == "AuthService"
    assert subj_node.type == "entity"

    # Check the edge
    edge = mock_add_edge.call_args_list[0][0][0]
    assert edge.source == "AuthService"
    assert edge.target == "UserDB"
    assert edge.relation == "calls"


def test_sync_from_memvid_empty_state(graph):
    storage = MagicMock()
    storage.state.return_value = {}

    with patch.object(graph, "add_node") as mock_add_node, \
         patch.object(graph, "add_edge") as mock_add_edge:
        graph.sync_from_memvid(storage)

    mock_add_node.assert_not_called()
    mock_add_edge.assert_not_called()


def test_close_closes_driver(graph):
    graph.close()
    graph._driver.close.assert_called_once()


def test_protocol_conformance(graph):
    assert isinstance(graph, GraphPlugin)


# ---------------------------------------------------------------------------
# GraphQL schema tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_strawberry(),
    reason="strawberry-graphql not installed (enterprise[neo4j] extra)",
)
def test_graphql_schema_has_query_type(mock_neo4j):
    from chronicler_enterprise.plugins.mnemon.graphql_server import GraphQLServer
    from chronicler_enterprise.plugins.mnemon.neo4j_graph import Neo4jGraph

    g = Neo4jGraph(uri="bolt://localhost:7687", auth=("neo4j", "test"))
    server = GraphQLServer(graph=g)

    schema_str = str(server.schema)
    assert "Query" in schema_str


@pytest.mark.skipif(
    not _has_strawberry(),
    reason="strawberry-graphql not installed (enterprise[neo4j] extra)",
)
def test_graphql_component_field_exists(mock_neo4j):
    from chronicler_enterprise.plugins.mnemon.graphql_server import GraphQLServer
    from chronicler_enterprise.plugins.mnemon.neo4j_graph import Neo4jGraph

    g = Neo4jGraph(uri="bolt://localhost:7687", auth=("neo4j", "test"))
    server = GraphQLServer(graph=g)

    schema_str = str(server.schema)
    assert "component" in schema_str
