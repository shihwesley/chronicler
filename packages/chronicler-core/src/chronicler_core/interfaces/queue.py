"""Queue plugin interface and models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    id: str = Field(min_length=1)
    payload: dict[str, Any]
    status: JobStatus = JobStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    attempts: int = Field(default=0, ge=0)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id cannot be empty or whitespace")
        return v


@runtime_checkable
class BasicQueue(Protocol):
    """Core queue operations: enqueue, dequeue, ack, nack."""

    def enqueue(self, job: Job) -> str: ...

    def dequeue(self) -> Job | None: ...

    def ack(self, job_id: str) -> None: ...

    def nack(self, job_id: str, reason: str) -> None: ...


@runtime_checkable
class DeadLetterQueue(Protocol):
    """Access to jobs that exhausted their retry budget."""

    def dead_letters(self) -> list[Job]: ...


@runtime_checkable
class QueuePlugin(BasicQueue, DeadLetterQueue, Protocol):
    """Full queue with both basic operations and dead-letter access.

    Kept for backward compatibility. New code should depend on BasicQueue
    or DeadLetterQueue individually where possible.
    """

    ...
