"""Tests for cloud queue plugins -- SQS, Pub/Sub, Service Bus.

Cloud SDK packages (boto3, google-cloud-pubsub, azure-servicebus) are not
installed in the test environment. We inject mock modules into sys.modules
before importing the implementation so the top-level imports succeed.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from chronicler_core.interfaces.queue import Job, JobStatus, QueuePlugin


def _make_job(**overrides) -> Job:
    defaults = dict(
        id=str(uuid.uuid4()),
        payload={"repo": "acme/app"},
    )
    defaults.update(overrides)
    return Job(**defaults)


# ---------------------------------------------------------------------------
# Module-level mock injection
# ---------------------------------------------------------------------------

def _ensure_mock_module(name: str) -> MagicMock:
    """Insert a MagicMock into sys.modules for *name* if not already present."""
    if name not in sys.modules:
        mod = MagicMock()
        mod.__name__ = name
        mod.__path__ = []  # marks it as a package for sub-imports
        mod.__package__ = name
        sys.modules[name] = mod
    return sys.modules[name]


# boto3
_mock_boto3 = _ensure_mock_module("boto3")

# google.cloud.pubsub_v1
_mock_google = _ensure_mock_module("google")
_mock_google_cloud = _ensure_mock_module("google.cloud")
_mock_pubsub_v1 = _ensure_mock_module("google.cloud.pubsub_v1")
# Wire parent -> child so `from google.cloud import pubsub_v1` resolves correctly
_mock_google.cloud = _mock_google_cloud
_mock_google_cloud.pubsub_v1 = _mock_pubsub_v1

# azure.servicebus
_mock_azure = _ensure_mock_module("azure")
_mock_azure_sb = _ensure_mock_module("azure.servicebus")
_mock_azure.servicebus = _mock_azure_sb
_mock_azure_sb = sys.modules["azure.servicebus"]
# ServiceBusMessage needs to be a real-ish class so the implementation can
# instantiate it and set attributes on it.
_mock_azure_sb.ServiceBusMessage = type("ServiceBusMessage", (), {
    "__init__": lambda self, body: setattr(self, "_body", body),
    "application_properties": None,
})
_mock_azure_sb.ServiceBusClient = MagicMock()


# Now import the implementation modules (they'll pick up the mocked SDKs)
from chronicler_enterprise.plugins.cloud_queue.sqs import SQSQueue
from chronicler_enterprise.plugins.cloud_queue.pubsub import PubSubQueue
from chronicler_enterprise.plugins.cloud_queue.servicebus import ServiceBusQueue


# ---------------------------------------------------------------------------
# SQS
# ---------------------------------------------------------------------------


class TestSQSQueue:
    @pytest.fixture
    def sqs(self):
        mock_client = MagicMock()
        _mock_boto3.client.return_value = mock_client

        q = SQSQueue(
            queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
            dlq_url="https://sqs.us-east-1.amazonaws.com/123/test-dlq",
        )
        q._mock_client = mock_client
        yield q

    def test_protocol_conformance(self, sqs):
        assert isinstance(sqs, QueuePlugin)

    def test_enqueue_returns_job_id(self, sqs):
        job = _make_job(id="job-1")
        result = sqs.enqueue(job)
        assert result == "job-1"
        sqs._mock_client.send_message.assert_called_once()

    def test_enqueue_sends_correct_body(self, sqs):
        job = _make_job(id="job-2", payload={"key": "value"})
        sqs.enqueue(job)
        call_kwargs = sqs._mock_client.send_message.call_args[1]
        assert json.loads(call_kwargs["MessageBody"]) == {"key": "value"}

    def test_enqueue_sends_metadata_as_attributes(self, sqs):
        job = _make_job(id="job-3")
        sqs.enqueue(job)
        call_kwargs = sqs._mock_client.send_message.call_args[1]
        attrs = call_kwargs["MessageAttributes"]
        assert attrs["job_id"]["StringValue"] == "job-3"
        assert attrs["status"]["StringValue"] == "pending"

    def test_dequeue_returns_none_when_empty(self, sqs):
        sqs._mock_client.receive_message.return_value = {"Messages": []}
        assert sqs.dequeue() is None

    def test_dequeue_returns_job(self, sqs):
        job = _make_job(id="job-4")
        sqs._mock_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps(job.payload),
                    "ReceiptHandle": "receipt-1",
                    "MessageAttributes": {
                        "job_id": {"DataType": "String", "StringValue": job.id},
                        "status": {"DataType": "String", "StringValue": "pending"},
                        "created_at": {
                            "DataType": "String",
                            "StringValue": job.created_at.isoformat(),
                        },
                        "updated_at": {
                            "DataType": "String",
                            "StringValue": job.updated_at.isoformat(),
                        },
                        "attempts": {"DataType": "Number", "StringValue": "0"},
                        "error": {"DataType": "String", "StringValue": ""},
                    },
                }
            ]
        }
        got = sqs.dequeue()
        assert got is not None
        assert got.id == "job-4"
        assert got.status == JobStatus.processing
        assert got.payload == {"repo": "acme/app"}

    def test_ack_deletes_message(self, sqs):
        sqs._receipts["job-5"] = "receipt-5"
        sqs.ack("job-5")
        sqs._mock_client.delete_message.assert_called_once_with(
            QueueUrl=sqs._queue_url,
            ReceiptHandle="receipt-5",
        )

    def test_ack_missing_receipt_is_noop(self, sqs):
        sqs.ack("nonexistent")
        sqs._mock_client.delete_message.assert_not_called()

    def test_nack_resets_visibility(self, sqs):
        sqs._receipts["job-6"] = "receipt-6"
        sqs.nack("job-6", "transient error")
        sqs._mock_client.change_message_visibility.assert_called_once_with(
            QueueUrl=sqs._queue_url,
            ReceiptHandle="receipt-6",
            VisibilityTimeout=0,
        )

    def test_dead_letters_no_dlq(self):
        mock_client = MagicMock()
        _mock_boto3.client.return_value = mock_client
        q = SQSQueue(queue_url="https://sqs.example.com/q")
        assert q.dead_letters() == []

    def test_dead_letters_reads_dlq(self, sqs):
        job = _make_job(id="dead-1")
        sqs._mock_client.receive_message.side_effect = [
            {
                "Messages": [
                    {
                        "Body": json.dumps(job.payload),
                        "ReceiptHandle": "r-dlq",
                        "MessageAttributes": {
                            "job_id": {"DataType": "String", "StringValue": "dead-1"},
                            "status": {"DataType": "String", "StringValue": "failed"},
                            "created_at": {
                                "DataType": "String",
                                "StringValue": job.created_at.isoformat(),
                            },
                            "updated_at": {
                                "DataType": "String",
                                "StringValue": job.updated_at.isoformat(),
                            },
                            "attempts": {"DataType": "Number", "StringValue": "3"},
                            "error": {
                                "DataType": "String",
                                "StringValue": "max retries",
                            },
                        },
                    }
                ]
            },
            {"Messages": []},
        ]
        dead = sqs.dead_letters()
        assert len(dead) == 1
        assert dead[0].id == "dead-1"
        assert dead[0].status == JobStatus.dead


# ---------------------------------------------------------------------------
# Pub/Sub
# ---------------------------------------------------------------------------


class TestPubSubQueue:
    @pytest.fixture
    def pubsub(self):
        mock_publisher = MagicMock()
        mock_subscriber = MagicMock()
        _mock_pubsub_v1.PublisherClient.return_value = mock_publisher
        _mock_pubsub_v1.SubscriberClient.return_value = mock_subscriber

        q = PubSubQueue(
            project_id="test-project",
            topic="test-topic",
            subscription="test-sub",
        )
        q._mock_publisher = mock_publisher
        q._mock_subscriber = mock_subscriber
        yield q

    def test_protocol_conformance(self, pubsub):
        assert isinstance(pubsub, QueuePlugin)

    def test_enqueue_returns_job_id(self, pubsub):
        job = _make_job(id="ps-1")
        result = pubsub.enqueue(job)
        assert result == "ps-1"
        pubsub._mock_publisher.publish.assert_called_once()

    def test_enqueue_publishes_correct_data(self, pubsub):
        job = _make_job(id="ps-2", payload={"x": 1})
        pubsub.enqueue(job)
        call_args = pubsub._mock_publisher.publish.call_args
        assert call_args[0][0] == pubsub._topic_path
        body = json.loads(call_args[1]["data"].decode("utf-8"))
        assert body == {"x": 1}

    def test_dequeue_returns_none_when_empty(self, pubsub):
        resp = MagicMock()
        resp.received_messages = []
        pubsub._mock_subscriber.pull.return_value = resp
        assert pubsub.dequeue() is None

    def test_dequeue_returns_job(self, pubsub):
        job = _make_job(id="ps-3")
        received_msg = MagicMock()
        received_msg.ack_id = "ack-1"
        received_msg.message.data = json.dumps(job.payload).encode("utf-8")
        received_msg.message.attributes = {
            "job_id": "ps-3",
            "status": "pending",
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "attempts": "0",
            "error": "",
        }
        resp = MagicMock()
        resp.received_messages = [received_msg]
        pubsub._mock_subscriber.pull.return_value = resp

        got = pubsub.dequeue()
        assert got is not None
        assert got.id == "ps-3"
        assert got.status == JobStatus.processing

    def test_ack_acknowledges_message(self, pubsub):
        pubsub._ack_ids["ps-4"] = "ack-4"
        pubsub.ack("ps-4")
        pubsub._mock_subscriber.acknowledge.assert_called_once_with(
            subscription=pubsub._subscription_path,
            ack_ids=["ack-4"],
        )

    def test_ack_missing_id_is_noop(self, pubsub):
        pubsub.ack("nonexistent")
        pubsub._mock_subscriber.acknowledge.assert_not_called()

    def test_nack_modifies_ack_deadline(self, pubsub):
        pubsub._ack_ids["ps-5"] = "ack-5"
        pubsub.nack("ps-5", "bad data")
        pubsub._mock_subscriber.modify_ack_deadline.assert_called_once_with(
            subscription=pubsub._subscription_path,
            ack_ids=["ack-5"],
            ack_deadline_seconds=0,
        )

    def test_dead_letters_returns_empty(self, pubsub):
        assert pubsub.dead_letters() == []


# ---------------------------------------------------------------------------
# Service Bus
# ---------------------------------------------------------------------------


class TestServiceBusQueue:
    @pytest.fixture
    def sb(self):
        mock_client = MagicMock()
        _mock_azure_sb.ServiceBusClient.from_connection_string.return_value = (
            mock_client
        )
        mock_sender = MagicMock()
        mock_receiver = MagicMock()
        mock_client.get_queue_sender.return_value = mock_sender
        mock_client.get_queue_receiver.return_value = mock_receiver

        q = ServiceBusQueue(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKey=abc",
            queue_name="test-queue",
        )
        q._mock_sender = mock_sender
        q._mock_receiver = mock_receiver
        yield q

    def test_protocol_conformance(self, sb):
        assert isinstance(sb, QueuePlugin)

    def test_enqueue_returns_job_id(self, sb):
        job = _make_job(id="sb-1")
        result = sb.enqueue(job)
        assert result == "sb-1"
        sb._mock_sender.send_messages.assert_called_once()

    def test_enqueue_message_has_correct_properties(self, sb):
        job = _make_job(id="sb-2", payload={"a": "b"})
        sb.enqueue(job)
        call_args = sb._mock_sender.send_messages.call_args
        sent_msg = call_args[0][0]
        assert sent_msg.application_properties["job_id"] == "sb-2"

    def test_dequeue_returns_none_when_empty(self, sb):
        sb._mock_receiver.receive_messages.return_value = []
        assert sb.dequeue() is None

    def test_dequeue_returns_job(self, sb):
        job = _make_job(id="sb-3")
        raw_msg = MagicMock()
        raw_msg.application_properties = {
            "job_id": "sb-3",
            "status": "pending",
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "attempts": "0",
            "error": "",
        }
        raw_msg.body = json.dumps(job.payload)
        sb._mock_receiver.receive_messages.return_value = [raw_msg]

        got = sb.dequeue()
        assert got is not None
        assert got.id == "sb-3"
        assert got.status == JobStatus.processing

    def test_ack_completes_message(self, sb):
        raw_msg = MagicMock()
        sb._messages["sb-4"] = raw_msg
        sb.ack("sb-4")
        sb._mock_receiver.complete_message.assert_called_once_with(raw_msg)

    def test_ack_missing_message_is_noop(self, sb):
        sb.ack("nonexistent")
        sb._mock_receiver.complete_message.assert_not_called()

    def test_nack_abandons_message(self, sb):
        raw_msg = MagicMock()
        sb._messages["sb-5"] = raw_msg
        sb.nack("sb-5", "something went wrong")
        sb._mock_receiver.abandon_message.assert_called_once_with(raw_msg)

    def test_dead_letters_returns_empty(self, sb):
        assert sb.dead_letters() == []
