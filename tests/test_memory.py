"""C.17 — Match Memory (Section 17)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fie.memory import remember, replay


@given(minutes=st.lists(st.floats(0, 90), min_size=1, max_size=30))
def test_replay_sorted(minutes):
    """T-17-01: replay always returns entries sorted by minute."""
    timeline = []
    for i, m in enumerate(minutes):
        remember(timeline, m, f"event {i}")
    out = replay(timeline)
    assert [e["minute"] for e in out] == sorted(minutes)


def test_remember_does_not_mutate_earlier():
    """T-17-02: remember appends without mutating earlier entries."""
    timeline = []
    remember(timeline, 12, "Brazil started pressing", "left channel")
    first = dict(timeline[0])
    remember(timeline, 31, "momentum shift")
    remember(timeline, 43, "Brazil in full control")
    assert timeline[0] == first
    assert len(timeline) == 3
