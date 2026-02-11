"""QueuePlugin implementation backed by Google Cloud Pub/Sub."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from google.cloud import pubsub_v1

from chronicler_core.interfaces.queue import Job, JobStatus

from ._serialization import attrs_to_job, job_to_attrs

logger = logging.getLogger(__name__)


class PubSubQueue:
    """Google Cloud Pub/Sub queue that conforms to the QueuePlugin protocol.

    Publishes to a topic, pulls from a subscription. Job metadata is stored
    as Pub/Sub message attributes; the payload goes in the message body.
    """

    def __init__(self, project_id: str, topic: str, subscription: str) -> None:
        self._project_id = project_id
        self._topic_path = f"projects/{project_id}/topics/{topic}"
        self._subscription_path = (
            f"projects/{project_id}/subscriptions/{subscription}"
        )
        self._publisher = pubsub_v1.PublisherClient()
        self._subscriber = pubsub_v1.SubscriberClient()
        # ack_id cache: job_id -> ack_id
        self._ack_ids: dict[str, str] = {}

    def close(self) -> None:
        self._publisher.transport.close()
        self._subscriber.close()

    # -- serialization helpers ------------------------------------------------

    @staticmethod
    def _message_to_job(msg) -> Job:
        return attrs_to_job(dict(msg.attributes), json.loads(msg.data.decode("utf-8")))

    # -- QueuePlugin protocol -------------------------------------------------

    def enqueue(self, job: Job) -> str:
        data = json.dumps(job.payload).encode("utf-8")
        attrs = job_to_attrs(job)
        self._publisher.publish(self._topic_path, data=data, **attrs)
        return job.id

    def dequeue(self) -> Job | None:
        resp = self._subscriber.pull(
            subscription=self._subscription_path,
            max_messages=1,
        )
        if not resp.received_messages:
            return None

        received = resp.received_messages[0]
        job = self._message_to_job(received.message)
        job.status = JobStatus.processing
        job.updated_at = datetime.now(UTC)
        self._ack_ids[job.id] = received.ack_id
        return job

    def ack(self, job_id: str) -> None:
        ack_id = self._ack_ids.pop(job_id, None)
        if ack_id is None:
            return
        self._subscriber.acknowledge(
            subscription=self._subscription_path,
            ack_ids=[ack_id],
        )

    def nack(self, job_id: str, reason: str) -> None:
        logger.warning("nack job=%s reason=%s", job_id, reason)
        ack_id = self._ack_ids.pop(job_id, None)
        if ack_id is None:
            return
        self._subscriber.modify_ack_deadline(
            subscription=self._subscription_path,
            ack_ids=[ack_id],
            ack_deadline_seconds=0,
        )

    def dead_letters(self) -> list[Job]:
        # Pub/Sub dead-letter topics are configured server-side.
        # This client-side implementation returns an empty list; dead letters
        # would be consumed from a separate dead-letter subscription.
        return []
