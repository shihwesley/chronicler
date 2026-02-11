"""QueuePlugin implementation backed by AWS SQS."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import boto3

from chronicler_core.interfaces.queue import Job, JobStatus

from ._serialization import attrs_to_job, job_to_attrs

logger = logging.getLogger(__name__)


class SQSQueue:
    """AWS SQS queue that conforms to the QueuePlugin protocol.

    Uses SQS message attributes to carry job metadata (status, timestamps,
    attempts). The message body holds the JSON-serialized payload.
    """

    def __init__(
        self,
        queue_url: str,
        region: str = "us-east-1",
        dlq_url: str | None = None,
        **boto_kwargs,
    ) -> None:
        self._queue_url = queue_url
        self._dlq_url = dlq_url
        self._client = boto3.client("sqs", region_name=region, **boto_kwargs)
        # receipt handle cache: job_id -> receipt_handle (needed for ack/nack)
        self._receipts: dict[str, str] = {}

    # -- serialization helpers ------------------------------------------------

    @staticmethod
    def _job_to_message(job: Job) -> dict:
        attrs = job_to_attrs(job)
        # SQS wraps each attribute in DataType/StringValue
        sqs_attrs = {}
        for key, val in attrs.items():
            dtype = "Number" if key == "attempts" else "String"
            sqs_attrs[key] = {"DataType": dtype, "StringValue": val}
        return {
            "MessageBody": json.dumps(job.payload),
            "MessageAttributes": sqs_attrs,
        }

    @staticmethod
    def _message_to_job(msg: dict) -> Job:
        raw = msg["MessageAttributes"]
        # Unwrap SQS DataType/StringValue back to flat dict
        attrs = {k: v["StringValue"] for k, v in raw.items()}
        return attrs_to_job(attrs, json.loads(msg["Body"]))

    # -- QueuePlugin protocol -------------------------------------------------

    def enqueue(self, job: Job) -> str:
        msg = self._job_to_message(job)
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=msg["MessageBody"],
            MessageAttributes=msg["MessageAttributes"],
        )
        return job.id

    def dequeue(self) -> Job | None:
        resp = self._client.receive_message(
            QueueUrl=self._queue_url,
            MessageAttributeNames=["All"],
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
        )
        messages = resp.get("Messages", [])
        if not messages:
            return None

        msg = messages[0]
        job = self._message_to_job(msg)
        job.status = JobStatus.processing
        job.updated_at = datetime.now(UTC)
        self._receipts[job.id] = msg["ReceiptHandle"]
        return job

    def ack(self, job_id: str) -> None:
        receipt = self._receipts.pop(job_id, None)
        if receipt is None:
            return
        self._client.delete_message(
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt,
        )

    def nack(self, job_id: str, reason: str) -> None:
        logger.warning("nack job=%s reason=%s", job_id, reason)
        receipt = self._receipts.pop(job_id, None)
        if receipt is None:
            return

        self._client.change_message_visibility(
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt,
            VisibilityTimeout=0,
        )

    def dead_letters(self, max_results: int = 1000) -> list[Job]:
        if not self._dlq_url:
            return []

        jobs: list[Job] = []
        while len(jobs) < max_results:
            batch_size = min(10, max_results - len(jobs))
            resp = self._client.receive_message(
                QueueUrl=self._dlq_url,
                MessageAttributeNames=["All"],
                MaxNumberOfMessages=batch_size,
                WaitTimeSeconds=0,
            )
            messages = resp.get("Messages", [])
            if not messages:
                break
            for msg in messages:
                job = self._message_to_job(msg)
                job.status = JobStatus.dead
                jobs.append(job)
        return jobs
