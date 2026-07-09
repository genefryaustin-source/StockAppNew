
"""
execution_bus.py

Institutional Execution Event Bus

Provides synchronous publish/subscribe for execution events.
Future versions can be extended to async queues, Kafka, Redis Streams,
or other messaging backends without changing callers.
"""

from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Callable, DefaultDict, Dict, List

from .execution_models import ExecutionEvent


class ExecutionBus:
    """
    Lightweight in-process execution event bus.

    Subscribers may subscribe to a specific event type
    (e.g. "ORDER_FILLED") or "*" for all events.
    """

    def __init__(self):
        self._subscriptions: DefaultDict[str, List[Callable[[ExecutionEvent], None]]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, topic: str, callback: Callable[[ExecutionEvent], None]) -> None:
        with self._lock:
            if callback not in self._subscriptions[topic]:
                self._subscriptions[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable[[ExecutionEvent], None]) -> None:
        with self._lock:
            if callback in self._subscriptions.get(topic, []):
                self._subscriptions[topic].remove(callback)

    def publish(self, event: ExecutionEvent) -> None:
        topic = event.event_type.value

        callbacks: List[Callable[[ExecutionEvent], None]] = []

        with self._lock:
            callbacks.extend(self._subscriptions.get(topic, []))
            callbacks.extend(self._subscriptions.get("*", []))

        for callback in callbacks:
            callback(event)

    def clear(self) -> None:
        with self._lock:
            self._subscriptions.clear()

    def subscription_counts(self) -> Dict[str, int]:
        with self._lock:
            return {
                topic: len(callbacks)
                for topic, callbacks in self._subscriptions.items()
            }
