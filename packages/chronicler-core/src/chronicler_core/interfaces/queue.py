"""Queue plugin interface and models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    """Lifecycle states for a queued job."""

    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    dead = "dead"


class Job(BaseModel):
    """A unit of work tracked by the queue.

    Mutable — status, timestamps, error, and attempts change over the job's lifetime.
    """

    id: str
    payload: dict[str, Any]
    status: JobStatus = JobStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    attempts: int = 0


@runtime_checkable
class QueuePlugin(Protocol):
    """Async job queue used by the orchestrator."""

    def enqueue(self, job: Job) -> str: ...

    def dequeue(self) -> Job | None: ...

    def ack(self, job_id: str) -> None: ...

    def nack(self, job_id: str, reason: str) -> None: ...

    def dead_letters(self) -> list[Job]: ...
