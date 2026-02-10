"""Shared Job serialization for cloud queue plugins."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from chronicler_core.interfaces.queue import Job, JobStatus


def job_to_attrs(job: Job) -> dict[str, str]:
    """Serialize Job metadata to a flat string dict (common across all cloud queues)."""
    return {
        "job_id": job.id,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "attempts": str(job.attempts),
        "error": job.error or "",
    }


def attrs_to_job(attrs: dict[str, Any], payload: dict) -> Job:
    """Deserialize Job from a flat string dict + payload."""
    error = attrs["error"]
    return Job(
        id=attrs["job_id"],
        payload=payload,
        status=JobStatus(attrs["status"]),
        created_at=datetime.fromisoformat(attrs["created_at"]),
        updated_at=datetime.fromisoformat(attrs["updated_at"]),
        error=error if error else None,
        attempts=int(attrs["attempts"]),
    )
