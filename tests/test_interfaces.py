"""Tests for chronicler_core.interfaces — model round-trips, enums, and structural subtyping."""

from __future__ import annotations

from datetime import datetime

import pytest

from chronicler_core.interfaces import (
    GraphEdge,
    GraphNode,
    GraphPlugin,
    Job,
    JobStatus,
    Permission,
    QueuePlugin,
    RBACPlugin,
    SearchResult,
    StoragePlugin,
)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestJobStatusEnum:
    def test_members(self):
        assert set(JobStatus) == {
            JobStatus.pending,
            JobStatus.processing,
            JobStatus.completed,
            JobStatus.failed,
            JobStatus.dead,
        }

    def test_string_values(self):
        for member in JobStatus:
            assert member.value == member.name


# ---------------------------------------------------------------------------
# Model serialization round-trips
# ---------------------------------------------------------------------------


class TestJobModel:
    def test_round_trip(self):
        job = Job(id="j-1", payload={"repo": "acme/app"}, attempts=2)
        data = job.model_dump_json()
        restored = Job.model_validate_json(data)
        assert restored.id == job.id
        assert restored.payload == job.payload
        assert restored.status == JobStatus.pending
        assert restored.attempts == 2

    def test_mutable_status(self):
        job = Job(id="j-2", payload={})
        job.status = JobStatus.processing
        assert job.status == JobStatus.processing

    def test_defaults(self):
        job = Job(id="j-3", payload={"x": 1})
        assert job.status == JobStatus.pending
        assert job.error is None
        assert job.attempts == 0
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)


class TestGraphNodeModel:
    def test_round_trip(self):
        node = GraphNode(id="n1", type="service", label="API", metadata={"lang": "py"})
        data = node.model_dump_json()
        restored = GraphNode.model_validate_json(data)
        assert restored == node

    def test_frozen(self):
        node = GraphNode(id="n2", type="lib", label="Core")
        with pytest.raises(Exception):
            node.id = "changed"


class TestGraphEdgeModel:
    def test_round_trip(self):
        edge = GraphEdge(source="a", target="b", relation="depends_on", metadata={"weight": 1})
        data = edge.model_dump_json()
        restored = GraphEdge.model_validate_json(data)
        assert restored == edge

    def test_frozen(self):
        edge = GraphEdge(source="a", target="b", relation="calls")
        with pytest.raises(Exception):
            edge.source = "c"


class TestPermissionModel:
    def test_round_trip(self):
        perm = Permission(resource="repo:acme/*", action="write", conditions={"branch": "main"})
        data = perm.model_dump_json()
        restored = Permission.model_validate_json(data)
        assert restored == perm

    def test_frozen(self):
        perm = Permission(resource="doc", action="read")
        with pytest.raises(Exception):
            perm.action = "write"


class TestSearchResultModel:
    def test_round_trip(self):
        sr = SearchResult(doc_id="d1", content="hello world", score=0.95, metadata={"src": "vcs"})
        data = sr.model_dump_json()
        restored = SearchResult.model_validate_json(data)
        assert restored == sr

    def test_frozen(self):
        sr = SearchResult(doc_id="d2", content="x", score=0.5)
        with pytest.raises(Exception):
            sr.score = 1.0


# ---------------------------------------------------------------------------
# Protocol structural subtyping (runtime_checkable)
# ---------------------------------------------------------------------------


class DummyQueue:
    def enqueue(self, job: Job) -> str:
        return job.id

    def dequeue(self) -> Job | None:
        return None

    def ack(self, job_id: str) -> None:
        pass

    def nack(self, job_id: str, reason: str) -> None:
        pass

    def dead_letters(self) -> list[Job]:
        return []


class DummyGraph:
    def add_node(self, node: GraphNode) -> None:
        pass

    def add_edge(self, edge: GraphEdge) -> None:
        pass

    def neighbors(self, node_id: str, depth: int = 1) -> list[GraphNode]:
        return []

    def query(self, expression: str) -> list[dict]:
        return []


class DummyRBAC:
    def check(self, user_id: str, permission: Permission) -> bool:
        return True

    def grant(self, user_id: str, permission: Permission) -> None:
        pass

    def revoke(self, user_id: str, permission: Permission) -> None:
        pass

    def list_permissions(self, user_id: str) -> list[Permission]:
        return []


class DummyStorage:
    def store(self, doc_id: str, content: str, metadata: dict) -> None:
        pass

    def search(self, query: str, k: int = 10, mode: str = "auto") -> list[SearchResult]:
        return []

    def get(self, doc_id: str) -> str | None:
        return None

    def state(self, entity: str) -> dict:
        return {}


class TestProtocolSubtyping:
    def test_queue_protocol(self):
        assert isinstance(DummyQueue(), QueuePlugin)

    def test_graph_protocol(self):
        assert isinstance(DummyGraph(), GraphPlugin)

    def test_rbac_protocol(self):
        assert isinstance(DummyRBAC(), RBACPlugin)

    def test_storage_protocol(self):
        assert isinstance(DummyStorage(), StoragePlugin)

    def test_non_conforming_rejected(self):
        """An object missing required methods should not match the Protocol."""

        class Incomplete:
            def enqueue(self, job: Job) -> str:
                return ""

        assert not isinstance(Incomplete(), QueuePlugin)
