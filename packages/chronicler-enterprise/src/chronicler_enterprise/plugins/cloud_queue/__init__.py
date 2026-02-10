"""Cloud queue plugin implementations (SQS, Pub/Sub, Service Bus).

Uses PEP 562 lazy imports so cloud SDKs are only loaded when accessed.
"""

__all__ = ["SQSQueue", "PubSubQueue", "ServiceBusQueue"]


def __getattr__(name: str):
    import importlib

    # Lazy-load submodules (needed for unittest.mock.patch resolution)
    _submodules = {"sqs", "pubsub", "servicebus"}
    if name in _submodules:
        return importlib.import_module(f".{name}", __name__)

    # Lazy-load classes so cloud SDKs aren't imported until first use
    _class_map = {
        "SQSQueue": ".sqs",
        "PubSubQueue": ".pubsub",
        "ServiceBusQueue": ".servicebus",
    }
    if name in _class_map:
        mod = importlib.import_module(_class_map[name], __name__)
        return getattr(mod, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
