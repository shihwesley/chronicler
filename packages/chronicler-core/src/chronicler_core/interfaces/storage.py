"""Storage plugin interface and models."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class SearchResult(BaseModel):
    """A single hit returned by a storage search."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    content: str
    score: float
    metadata: dict[str, Any] = {}


@runtime_checkable
class StoragePlugin(Protocol):
    """Document storage and retrieval backend (vector, full-text, or hybrid)."""

    def store(self, doc_id: str, content: str, metadata: dict) -> None: ...

    def search(self, query: str, k: int = 10, mode: str = "auto") -> list[SearchResult]: ...

    def get(self, doc_id: str) -> str | None: ...

    def state(self, entity: str) -> dict: ...
