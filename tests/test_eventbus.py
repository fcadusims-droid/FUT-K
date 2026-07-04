"""Event bus — deterministic, ordered, decoupled pub/sub."""

from __future__ import annotations

from fie.eventbus import EventBus


def test_ordered_delivery_and_return_values():
    bus = EventBus()
    seen = []
    bus.subscribe("obs", lambda p: seen.append(("a", p)) or f"a{p}")
    bus.subscribe("obs", lambda p: seen.append(("b", p)) or f"b{p}")
    results = bus.publish("obs", 1)
    # Handlers fire in subscription order; return values gathered in order.
    assert seen == [("a", 1), ("b", 1)]
    assert results == ["a1", "b1"]


def test_unknown_topic_and_unsubscribe():
    bus = EventBus()
    hits = []
    h = lambda p: hits.append(p)
    bus.subscribe("x", h)
    assert bus.publish("nope", 1) == []       # no subscribers -> nobody
    bus.publish("x", 1)
    bus.unsubscribe("x", h)
    bus.publish("x", 2)
    assert hits == [1]                          # only the pre-unsubscribe event
    assert bus.topics() == []


def test_deterministic():
    def build():
        bus = EventBus()
        out = []
        bus.subscribe("t", lambda p: out.append(p * 2))
        bus.subscribe("t", lambda p: out.append(p + 1))
        for i in range(3):
            bus.publish("t", i)
        return out
    assert build() == build() == [0, 1, 2, 2, 4, 3]
