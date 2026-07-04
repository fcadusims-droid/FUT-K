"""A tiny deterministic event bus (Core): one event, many listeners.

``docs/ARCHITECTURE.md`` deferred the event bus until live multi-source feeds
arrived — Live Mode is that trigger. This is the smallest thing that could
possibly work: a synchronous, in-process publish/subscribe with **ordered,
deterministic** delivery (handlers fire in subscription order, every time).

Pure — imports nothing but the standard library, so it stays in Core. No
threads, no async, no I/O: the same purity that makes the panel reproducible
makes the bus reproducible. Real transport (a socket, a queue) is an
Application concern layered on top; the decoupling — publishers don't know
their subscribers — is the point.
"""

from __future__ import annotations

from collections import defaultdict


class EventBus:
    """Synchronous ordered pub/sub. Handlers are ``callable(payload) -> Any``."""

    def __init__(self) -> None:
        self._subs: dict = defaultdict(list)

    def subscribe(self, topic: str, handler) -> None:
        """Register ``handler`` for ``topic`` (may subscribe to many topics)."""
        self._subs[topic].append(handler)

    def unsubscribe(self, topic: str, handler) -> None:
        if handler in self._subs.get(topic, []):
            self._subs[topic].remove(handler)

    def publish(self, topic: str, payload) -> list:
        """Deliver ``payload`` to every subscriber of ``topic``, in order.

        Returns the list of handler return values (in subscription order) —
        useful for gathering derived state. Unknown topics deliver to nobody.
        """
        return [handler(payload) for handler in self._subs.get(topic, [])]

    def topics(self) -> list:
        return sorted(t for t, hs in self._subs.items() if hs)
