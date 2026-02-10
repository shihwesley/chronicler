"""Tests for SQLiteQueue — the local job queue backed by SQLite."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from chronicler_core.interfaces.queue import Job, JobStatus, QueuePlugin
from chronicler_lite.queue.sqlite_queue import SQLiteQueue


@pytest.fixture
def queue(tmp_path) -> SQLiteQueue:
    db = tmp_path / "test_queue.db"
    return SQLiteQueue(db_path=str(db))


def _make_job(**overrides) -> Job:
    defaults = dict(
        id=str(uuid.uuid4()),
        payload={"repo": "acme/app"},
    )
    defaults.update(overrides)
    return Job(**defaults)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_satisfies_queue_plugin(self, queue: SQLiteQueue):
        assert isinstance(queue, QueuePlugin)


# ---------------------------------------------------------------------------
# Enqueue / Dequeue
# ---------------------------------------------------------------------------


class TestEnqueueDequeue:
    def test_round_trip(self, queue: SQLiteQueue):
        job = _make_job()
        returned_id = queue.enqueue(job)
        assert returned_id == job.id

        got = queue.dequeue()
        assert got is not None
        assert got.id == job.id
        assert got.payload == {"repo": "acme/app"}
        assert got.status == JobStatus.processing

    def test_fifo_ordering(self, queue: SQLiteQueue):
        """Jobs come out in creation-time order."""
        base = datetime(2025, 1, 1, tzinfo=UTC)
        ids = []
        for i in range(5):
            j = _make_job(id=f"job-{i}", created_at=base + timedelta(seconds=i))
            queue.enqueue(j)
            ids.append(j.id)

        for expected_id in ids:
            got = queue.dequeue()
            assert got is not None
            assert got.id == expected_id

    def test_dequeue_empty_returns_none(self, queue: SQLiteQueue):
        assert queue.dequeue() is None

    def test_dequeue_skips_non_pending(self, queue: SQLiteQueue):
        """Only pending jobs are returned by dequeue."""
        j = _make_job()
        queue.enqueue(j)
        # Manually mark it completed so dequeue skips it
        queue.ack(j.id)
        assert queue.dequeue() is None


# ---------------------------------------------------------------------------
# Ack
# ---------------------------------------------------------------------------


class TestAck:
    def test_marks_completed(self, queue: SQLiteQueue):
        j = _make_job()
        queue.enqueue(j)
        queue.dequeue()  # moves to processing
        queue.ack(j.id)

        stats = queue.stats()
        assert stats["completed"] == 1
        assert stats["processing"] == 0


# ---------------------------------------------------------------------------
# Nack with retry
# ---------------------------------------------------------------------------


class TestNack:
    def test_retry_back_to_pending(self, queue: SQLiteQueue):
        j = _make_job()
        queue.enqueue(j)
        queue.dequeue()

        queue.nack(j.id, "transient error")
        stats = queue.stats()
        # Should be back in pending (attempt 1 < MAX_ATTEMPTS)
        assert stats["pending"] == 1
        assert stats["dead"] == 0

    def test_attempts_incremented(self, queue: SQLiteQueue):
        j = _make_job()
        queue.enqueue(j)

        # Fail once
        queue.dequeue()
        queue.nack(j.id, "fail 1")

        # Dequeue again (now pending again)
        got = queue.dequeue()
        assert got is not None
        assert got.attempts == 1

    def test_dead_letter_after_max_attempts(self, queue: SQLiteQueue):
        j = _make_job()
        queue.enqueue(j)

        for i in range(SQLiteQueue.MAX_ATTEMPTS):
            queue.dequeue()
            queue.nack(j.id, f"fail {i + 1}")

        stats = queue.stats()
        assert stats["dead"] == 1
        assert stats["pending"] == 0

    def test_nack_nonexistent_job_is_noop(self, queue: SQLiteQueue):
        # Should not raise
        queue.nack("no-such-id", "reason")


# ---------------------------------------------------------------------------
# Dead letters
# ---------------------------------------------------------------------------


class TestDeadLetters:
    def test_returns_only_dead_jobs(self, queue: SQLiteQueue):
        t1 = datetime(2025, 1, 1, tzinfo=UTC)
        t2 = datetime(2025, 1, 2, tzinfo=UTC)
        alive = _make_job(id="alive", created_at=t1)
        doomed = _make_job(id="doomed", created_at=t2)

        queue.enqueue(alive)
        queue.enqueue(doomed)

        # Process 'alive' normally (FIFO: it has earlier created_at)
        got = queue.dequeue()
        assert got.id == "alive"
        queue.ack(got.id)

        # Exhaust retries for 'doomed'
        for i in range(SQLiteQueue.MAX_ATTEMPTS):
            queue.dequeue()
            queue.nack(doomed.id, f"fail {i + 1}")

        dead = queue.dead_letters()
        assert len(dead) == 1
        assert dead[0].id == "doomed"

    def test_dead_letters_complete(self, queue: SQLiteQueue):
        """Exhaust a job's retries, then verify dead_letters returns it."""
        j = _make_job()
        queue.enqueue(j)

        for i in range(SQLiteQueue.MAX_ATTEMPTS):
            queue.dequeue()
            queue.nack(j.id, f"fail {i + 1}")

        dead = queue.dead_letters()
        assert len(dead) == 1
        assert dead[0].id == j.id
        assert dead[0].status == JobStatus.dead
        assert dead[0].error == f"fail {SQLiteQueue.MAX_ATTEMPTS}"
        assert dead[0].attempts == SQLiteQueue.MAX_ATTEMPTS

    def test_dead_letters_empty_when_none_dead(self, queue: SQLiteQueue):
        j = _make_job()
        queue.enqueue(j)
        assert queue.dead_letters() == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_all_statuses_present(self, queue: SQLiteQueue):
        stats = queue.stats()
        for status in JobStatus:
            assert status.value in stats

    def test_counts_correct(self, queue: SQLiteQueue):
        # 3 jobs: one completed, one processing, one pending
        j1, j2, j3 = _make_job(id="j1"), _make_job(id="j2"), _make_job(id="j3")
        queue.enqueue(j1)
        queue.enqueue(j2)
        queue.enqueue(j3)

        queue.dequeue()  # j1 -> processing
        queue.ack(j1.id)  # j1 -> completed
        queue.dequeue()  # j2 -> processing

        stats = queue.stats()
        assert stats["completed"] == 1
        assert stats["processing"] == 1
        assert stats["pending"] == 1


# ---------------------------------------------------------------------------
# Concurrent safety
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_two_dequeues_no_duplicates(self, tmp_path):
        """Two threads dequeueing simultaneously should never get the same job."""
        db = tmp_path / "concurrent.db"
        # Use a single job — only one thread should get it
        q1 = SQLiteQueue(db_path=str(db))
        j = _make_job()
        q1.enqueue(j)

        results: list[Job | None] = [None, None]

        def worker(idx: int) -> None:
            # Each thread needs its own connection
            q = SQLiteQueue(db_path=str(db))
            results[idx] = q.dequeue()

        t1 = threading.Thread(target=worker, args=(0,))
        t2 = threading.Thread(target=worker, args=(1,))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        got = [r for r in results if r is not None]
        # Exactly one thread should have claimed the job
        assert len(got) == 1
        assert got[0].id == j.id
