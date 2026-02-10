"""QueuePlugin implementation backed by a local SQLite database."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from chronicler_core.interfaces.queue import Job, JobStatus

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


class SQLiteQueue:
    """QueuePlugin implementation using SQLite with WAL mode.

    Stores jobs in a local SQLite database, suitable for single-machine
    batch processing without any cloud dependencies.
    """

    MAX_ATTEMPTS = 3

    def __init__(self, db_path: str = ".chronicler/queue.db") -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(path)
        # isolation_level=None => autocommit mode, giving us manual
        # transaction control for the atomic dequeue.
        self._conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=5)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    # -- helpers ---------------------------------------------------------------

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def _row_to_job(self, row: tuple) -> Job:
        id_, payload_json, status, created_at, updated_at, error, attempts = row
        return Job(
            id=id_,
            payload=json.loads(payload_json),
            status=JobStatus(status),
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            error=error,
            attempts=attempts,
        )

    # -- QueuePlugin protocol --------------------------------------------------

    def enqueue(self, job: Job) -> str:
        """Insert a job into the queue and return its id."""
        self._conn.execute(
            "INSERT INTO jobs (id, payload_json, status, created_at, updated_at, error, attempts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                job.id,
                json.dumps(job.payload),
                job.status.value,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
                job.error,
                job.attempts,
            ),
        )
        return job.id

    def dequeue(self) -> Job | None:
        """Atomically claim the oldest pending job and return it, or None.

        Uses BEGIN IMMEDIATE to hold a write lock for the duration of the
        select-then-update, preventing two connections from grabbing the
        same job.
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            row = cursor.execute(
                "SELECT id, payload_json, status, created_at, updated_at, error, attempts "
                "FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                (JobStatus.pending.value,),
            ).fetchone()
            if row is None:
                cursor.execute("COMMIT")
                return None

            now = self._now_iso()
            cursor.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (JobStatus.processing.value, now, row[0]),
            )
            cursor.execute("COMMIT")

            # Build the job object with the updated status/timestamp
            job = self._row_to_job(row)
            job.status = JobStatus.processing
            job.updated_at = datetime.fromisoformat(now)
            return job
        except Exception:
            self._conn.rollback()
            raise

    def ack(self, job_id: str) -> None:
        """Mark a job as completed."""
        self._conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (JobStatus.completed.value, self._now_iso(), job_id),
        )

    def nack(self, job_id: str, reason: str) -> None:
        """Reject a job. Re-queues it for retry, or sends it to dead letters."""
        cursor = self._conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            row = cursor.execute(
                "SELECT attempts FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                cursor.execute("COMMIT")
                return

            new_attempts = row[0] + 1
            if new_attempts >= self.MAX_ATTEMPTS:
                new_status = JobStatus.dead.value
            else:
                new_status = JobStatus.pending.value

            cursor.execute(
                "UPDATE jobs SET status = ?, error = ?, attempts = ?, updated_at = ? WHERE id = ?",
                (new_status, reason, new_attempts, self._now_iso(), job_id),
            )
            cursor.execute("COMMIT")
        except Exception:
            self._conn.rollback()
            raise

    def dead_letters(self) -> list[Job]:
        """Return all jobs that exhausted their retry budget."""
        rows = self._conn.execute(
            "SELECT id, payload_json, status, created_at, updated_at, error, attempts "
            "FROM jobs WHERE status = ? ORDER BY updated_at ASC",
            (JobStatus.dead.value,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    # -- extras ----------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        """Count jobs grouped by status."""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) FROM jobs GROUP BY status"
        ).fetchall()
        counts = {s.value: 0 for s in JobStatus}
        for status, count in rows:
            counts[status] = count
        return counts
