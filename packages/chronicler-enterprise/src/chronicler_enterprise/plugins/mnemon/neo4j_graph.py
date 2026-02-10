"""Neo4j implementation of the GraphPlugin protocol for Mnemon consumption."""

from __future__ import annotations

from typing import Any

from chronicler_core.interfaces.graph import GraphEdge, GraphNode
from chronicler_core.interfaces.storage import StoragePlugin


class Neo4jGraph:
    """Neo4j-backed knowledge graph.

    Lazy-imports the ``neo4j`` driver so the module can be imported even when
    the driver is not installed (optional dependency).
    """

    def __init__(self, uri: str, auth: tuple[str, str], database: str = "neo4j"):
        import neo4j

        self._driver = neo4j.GraphDatabase.driver(uri, auth=auth)
        self._database = database

    def close(self) -> None:
        self._driver.close()

    # -- GraphPlugin protocol --------------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        query = (
            "MERGE (n:Component {id: $id}) "
            "SET n.type = $type, n.label = $label, n += $metadata"
        )
        with self._driver.session(database=self._database) as session:
            session.run(
                query,
                id=node.id,
                type=node.type,
                label=node.label,
                metadata=node.metadata,
            )

    def add_edge(self, edge: GraphEdge) -> None:
        query = """
            MATCH (a:Component {id: $source}), (b:Component {id: $target})
            MERGE (a)-[r:RELATES {relation: $relation}]->(b)
            SET r += $metadata
        """
        with self._driver.session(database=self._database) as session:
            session.run(
                query,
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
                metadata=edge.metadata,
            )

    def neighbors(self, node_id: str, depth: int = 1) -> list[GraphNode]:
        query = (
            f"MATCH (n:Component {{id: $id}})-[*1..{depth}]-(m:Component) "
            "RETURN DISTINCT m"
        )
        with self._driver.session(database=self._database) as session:
            result = session.run(query, id=node_id)
            return [
                GraphNode(
                    id=r["m"]["id"],
                    type=r["m"].get("type", ""),
                    label=r["m"].get("label", ""),
                    metadata={
                        k: v
                        for k, v in r["m"].items()
                        if k not in ("id", "type", "label")
                    },
                )
                for r in result
            ]

    def query(self, expression: str) -> list[dict]:
        with self._driver.session(database=self._database) as session:
            result = session.run(expression)
            return [dict(record) for record in result]

    # -- Mnemon sync -----------------------------------------------------------

    def sync_from_memvid(self, storage: StoragePlugin) -> None:
        """Pull SPO triplets from MemVid storage and materialize them as graph nodes/edges."""
        state = storage.state("memory_cards")
        if not state or "cards" not in state:
            return

        for card in state["cards"]:
            subj = GraphNode(id=card["subject"], type="entity", label=card["subject"])
            obj = GraphNode(id=card["object"], type="entity", label=card["object"])
            edge = GraphEdge(
                source=card["subject"],
                target=card["object"],
                relation=card["predicate"],
            )
            self.add_node(subj)
            self.add_node(obj)
            self.add_edge(edge)
