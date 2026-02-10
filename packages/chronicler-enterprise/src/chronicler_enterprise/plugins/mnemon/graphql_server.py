"""Strawberry GraphQL server exposing the Neo4j graph for Mnemon consumption."""

from __future__ import annotations

from typing import TYPE_CHECKING

import strawberry

if TYPE_CHECKING:
    from strawberry.types import Info

    from .neo4j_graph import Neo4jGraph


@strawberry.type
class Component:
    id: str
    type: str
    label: str


@strawberry.type
class Edge:
    source: str
    target: str
    relation: str


@strawberry.type
class BlastRadiusResult:
    component: Component
    depth: int
    relationship: str


def _graph(info: Info) -> Neo4jGraph:
    return info.context["graph"]


@strawberry.type
class Query:
    @strawberry.field
    def component(self, info: Info, id: str) -> Component | None:
        rows = _graph(info).query(
            f"MATCH (n:Component {{id: '{id}'}}) RETURN n LIMIT 1"
        )
        if not rows:
            return None
        n = rows[0]["n"]
        return Component(id=n["id"], type=n.get("type", ""), label=n.get("label", ""))

    @strawberry.field
    def components(self, info: Info, type: str | None = None) -> list[Component]:
        if type:
            rows = _graph(info).query(
                f"MATCH (n:Component {{type: '{type}'}}) RETURN n"
            )
        else:
            rows = _graph(info).query("MATCH (n:Component) RETURN n")
        return [
            Component(id=r["n"]["id"], type=r["n"].get("type", ""), label=r["n"].get("label", ""))
            for r in rows
        ]

    @strawberry.field
    def edges(self, info: Info, source: str | None = None) -> list[Edge]:
        if source:
            rows = _graph(info).query(
                f"MATCH (a:Component {{id: '{source}'}})-[r:RELATES]->(b:Component) "
                "RETURN a.id AS src, b.id AS tgt, r.relation AS rel"
            )
        else:
            rows = _graph(info).query(
                "MATCH (a:Component)-[r:RELATES]->(b:Component) "
                "RETURN a.id AS src, b.id AS tgt, r.relation AS rel"
            )
        return [Edge(source=r["src"], target=r["tgt"], relation=r["rel"]) for r in rows]

    @strawberry.field
    def dependency_tree(self, info: Info, root_id: str, depth: int = 2) -> list[Component]:
        from chronicler_core.interfaces.graph import GraphNode

        nodes: list[GraphNode] = _graph(info).neighbors(root_id, depth=depth)
        return [Component(id=n.id, type=n.type, label=n.label) for n in nodes]

    @strawberry.field
    def blast_radius(self, info: Info, component_id: str, depth: int = 2) -> list[BlastRadiusResult]:
        # Walk neighbors at each depth level so we can tag the hop distance
        results: list[BlastRadiusResult] = []
        seen: set[str] = set()
        for d in range(1, depth + 1):
            nodes = _graph(info).neighbors(component_id, depth=d)
            for n in nodes:
                if n.id not in seen:
                    seen.add(n.id)
                    results.append(
                        BlastRadiusResult(
                            component=Component(id=n.id, type=n.type, label=n.label),
                            depth=d,
                            relationship="affects",
                        )
                    )
        return results


class GraphQLServer:
    """Thin wrapper that wires a strawberry schema to the Neo4jGraph instance."""

    def __init__(self, graph: Neo4jGraph, host: str = "0.0.0.0", port: int = 4000):
        self._graph = graph
        self._host = host
        self._port = port
        self._schema = strawberry.Schema(query=Query)

    def start(self) -> None:
        """Start the GraphQL server (blocking)."""
        from strawberry.asgi import GraphQL
        import uvicorn

        app = GraphQL(self._schema, context_getter=lambda: {"graph": self._graph})
        uvicorn.run(app, host=self._host, port=self._port)

    @property
    def schema(self) -> strawberry.Schema:
        return self._schema
