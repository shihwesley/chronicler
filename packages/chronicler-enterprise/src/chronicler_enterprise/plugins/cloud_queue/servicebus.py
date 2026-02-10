"""QueuePlugin implementation backed by Azure Service Bus."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from azure.servicebus import ServiceBusClient, ServiceBusMessage

from chronicler_core.interfaces.queue import Job, JobStatus


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

    # -- serialization helpers ------------------------------------------------

    @staticmethod
    def _job_to_message(job: Job) -> ServiceBusMessage:
        msg = ServiceBusMessage(json.dumps(job.payload))
        msg.application_properties = {
            "job_id": job.id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "attempts": str(job.attempts),
            "error": job.error or "",
        }
        return msg

    @staticmethod
    def _received_to_job(msg) -> Job:
        props = msg.application_properties
        error = props["error"]
        return Job(
            id=props["job_id"],
            payload=json.loads(str(msg)),
            status=JobStatus(props["status"]),
            created_at=datetime.fromisoformat(props["created_at"]),
            updated_at=datetime.fromisoformat(props["updated_at"]),
            error=error if error else None,
            attempts=int(props["attempts"]),
        )

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
