"""Graph plugin interface and models."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class GraphNode(BaseModel):
    """A node in the knowledge graph."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    label: str
    metadata: dict[str, Any] = {}


class GraphEdge(BaseModel):
    """A directed edge between two graph nodes."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relation: str
    metadata: dict[str, Any] = {}


@runtime_checkable
class GraphPlugin(Protocol):
    """Knowledge graph backend (e.g. Neo4j, in-memory)."""

    def add_node(self, node: GraphNode) -> None: ...

    def add_edge(self, edge: GraphEdge) -> None: ...

    def neighbors(self, node_id: str, depth: int = 1) -> list[GraphNode]: ...

    def query(self, expression: str) -> list[dict]: ...
