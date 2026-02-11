"""QueuePlugin implementation backed by Azure Service Bus."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from azure.servicebus import ServiceBusClient, ServiceBusMessage

from chronicler_core.interfaces.queue import Job, JobStatus

from ._serialization import attrs_to_job, job_to_attrs

logger = logging.getLogger(__name__)


class ServiceBusQueue:
    """Azure Service Bus queue that conforms to the QueuePlugin protocol.

    Uses a ServiceBusClient to send/receive messages. Job metadata is stored
    as application properties; the payload goes in the message body as JSON.
    """

    def __init__(self, connection_string: str, queue_name: str) -> None:
        self._queue_name = queue_name
        self._client = ServiceBusClient.from_connection_string(connection_string)
        self._sender = self._client.get_queue_sender(queue_name=queue_name)
        self._receiver = self._client.get_queue_receiver(queue_name=queue_name)
        # message cache: job_id -> ServiceBusReceivedMessage
        self._messages: dict[str, object] = {}

    def close(self) -> None:
        self._sender.close()
        self._receiver.close()
        self._client.close()

    # -- serialization helpers ------------------------------------------------

    @staticmethod
    def _job_to_message(job: Job) -> ServiceBusMessage:
        msg = ServiceBusMessage(json.dumps(job.payload))
        msg.application_properties = job_to_attrs(job)
        return msg

    @staticmethod
    def _received_to_job(msg) -> Job:
        return attrs_to_job(dict(msg.application_properties), json.loads(str(msg.body)))

    # -- QueuePlugin protocol -------------------------------------------------

    def enqueue(self, job: Job) -> str:
        msg = self._job_to_message(job)
        self._sender.send_messages(msg)
        return job.id

    def dequeue(self) -> Job | None:
        messages = self._receiver.receive_messages(max_message_count=1, max_wait_time=0)
        if not messages:
            return None

        raw = messages[0]
        job = self._received_to_job(raw)
        job.status = JobStatus.processing
        job.updated_at = datetime.now(UTC)
        self._messages[job.id] = raw
        return job

    def ack(self, job_id: str) -> None:
        msg = self._messages.pop(job_id, None)
        if msg is None:
            return
        self._receiver.complete_message(msg)

    def nack(self, job_id: str, reason: str) -> None:
        logger.warning("nack job=%s reason=%s", job_id, reason)
        msg = self._messages.pop(job_id, None)
        if msg is None:
            return
        self._receiver.abandon_message(msg)

    def dead_letters(self) -> list[Job]:
        # Azure Service Bus manages dead-letter sub-queues server-side.
        # To read them you'd open a receiver on "<queue>/$deadletterqueue".
        # This returns an empty list for now; a DLQ receiver could be added
        # as an optional init parameter.
        return []
