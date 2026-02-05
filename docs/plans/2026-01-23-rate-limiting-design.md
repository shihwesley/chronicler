# Rate Limiting & Queue Design for Chronicler

**Date:** 2026-01-23
**Status:** Proposed
**Author:** Claude + User

## Summary

Queue-based rate limiting for enterprise scale (500+ repos). Provider-agnostic queue interface supporting SQS, Pub/Sub, and Azure Service Bus.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Queue-based architecture | Handles bursts, resilient to failures, enterprise-ready |
| Cloud queue (not Redis/SQLite) | Managed, scalable, fits enterprise infra |
| Provider-agnostic interface | Let enterprise pick SQS/Pub-Sub/Service Bus |
| Dead letter queue | Failed jobs don't block pipeline |
| Worker pool | Configurable parallelism |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator API                      │
├─────────────────────────────────────────────────────────┤
│                    QueueInterface (ABC)                  │
├──────────┬──────────┬──────────────────────────────────┤
│   SQS    │ Pub/Sub  │ Azure Service Bus                 │
│ Adapter  │ Adapter  │ Adapter                           │
└────┬─────┴────┬─────┴────────┬──────────────────────────┘
     │          │              │
     ▼          ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                    Worker Pool                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                   │
│  │Worker 1 │ │Worker 2 │ │Worker N │ (configurable)    │
│  └─────────┘ └─────────┘ └─────────┘                   │
└─────────────────────────────────────────────────────────┘
```

## Message Types

```python
class MessageType(Enum):
    CRAWL_ORG = "crawl_org"      # Discover all repos in org
    CRAWL_REPO = "crawl_repo"    # Fetch metadata for single repo
    GENERATE_DOC = "generate_doc" # Run AI Drafter for repo
```

## Interface Contract

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class QueueMessage:
    type: MessageType
    payload: dict[str, Any]
    attempt: int = 0
    max_attempts: int = 3

@dataclass
class QueueConfig:
    provider: str  # "sqs" | "pubsub" | "servicebus"
    queue_url: str
    dlq_url: str   # dead letter queue
    visibility_timeout: int = 300  # 5 min
    max_workers: int = 5

class QueueInterface(ABC):
    def __init__(self, config: QueueConfig):
        self.config = config

    @abstractmethod
    def send(self, message: QueueMessage) -> str:
        """Send message, return message ID."""

    @abstractmethod
    def receive(self, max_messages: int = 1) -> list[tuple[str, QueueMessage]]:
        """Receive messages, return (receipt_handle, message) pairs."""

    @abstractmethod
    def delete(self, receipt_handle: str) -> None:
        """Delete processed message."""

    @abstractmethod
    def send_to_dlq(self, message: QueueMessage, error: str) -> None:
        """Send failed message to dead letter queue."""
```

## Factory

```python
def create_queue(config: QueueConfig) -> QueueInterface:
    match config.provider:
        case "sqs": return SQSAdapter(config)
        case "pubsub": return PubSubAdapter(config)
        case "servicebus": return ServiceBusAdapter(config)
        case _: raise ValueError(f"Unknown provider: {config.provider}")
```

## Rate Limit Handling

Workers monitor GitHub API rate limits via response headers:

```python
class GitHubWorker:
    def process(self, message: QueueMessage):
        response = self.github.make_request(...)

        remaining = int(response.headers["X-RateLimit-Remaining"])
        reset_at = int(response.headers["X-RateLimit-Reset"])

        if remaining < 100:
            sleep_seconds = reset_at - time.time()
            logger.warning(f"Rate limit low, sleeping {sleep_seconds}s")
            time.sleep(max(0, sleep_seconds))
```

## Retry Logic

- Max 3 attempts per message
- Exponential backoff between attempts
- After 3 failures → dead letter queue
- DLQ messages require manual review/replay

## Dependencies

```
boto3>=1.35.0        # AWS SQS
google-cloud-pubsub  # GCP Pub/Sub (optional)
azure-servicebus     # Azure (optional)
```

## Future Work

- Priority queues for critical repos
- Batch operations (send_batch, delete_batch)
- Metrics/observability (queue depth, processing time)
