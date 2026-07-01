"""C.7 — Index engine (Section 7)."""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from fie.events import Event
from fie.indices import (
    EVENT_WEIGHT,
    momentum_index,
    offensive_pressure,
    time_weight,
)

OFFENSIVE_TYPES = list(EVENT_WEIGHT) + ["pass", "foul"]  # last two carry no weight


def _event(team, minute, etype="shot"):
    return Event(match_id="t", minute=float(minute), team=team, type=etype)


events_strategy = st.lists(
    st.builds(
        _event,
        st.sampled_from(["HOME", "AWAY"]),
        st.floats(min_value=0, max_value=90),
        st.sampled_from(OFFENSIVE_TYPES),
    ),
    max_size=40,
)


@given(events=events_strategy, tau=st.floats(min_value=0.1, max_value=60))
@settings(max_examples=1000)
def test_momentum_in_unit_interval(events, tau):
    """T-07-01: momentum_index is always in [0, 1]."""
    m = momentum_index(events, current_minute=90, tau=tau)
    assert 0.0 <= m <= 1.0


def test_momentum_empty_is_half():
    """T-07-02: with zero events, momentum is exactly 0.5."""
    assert momentum_index([], current_minute=30, tau=8) == 0.5


@given(
    events=events_strategy,
    tau=st.floats(min_value=0.5, max_value=30),
    minute=st.floats(min_value=0, max_value=90),
)
def test_offensive_pressure_monotonic(events, tau, minute):
    """T-07-03: pressure is non-decreasing as more same-team events are added."""
    before = offensive_pressure(events, "HOME", minute, tau)
    extra = _event("HOME", minute, "shot_on_target")
    after = offensive_pressure(events + [extra], "HOME", minute, tau)
    assert after >= before - 1e-12


def test_exponential_decay_halves():
    """T-07-04: an event at t - tau*ln(2) weighs exactly half of one at t."""
    tau, t = 8.0, 50.0
    half = time_weight(t, t - tau * math.log(2), tau)
    full = time_weight(t, t, tau)
    assert math.isclose(half / full, 0.5, abs_tol=1e-9)


def test_recent_shots_dominate_momentum():
    """T-07-05: HOME dominating recently with shots on target -> momentum > 0.9."""
    events = [_event("HOME", m, "shot_on_target") for m in (86, 87, 88, 89, 90)]
    assert momentum_index(events, current_minute=90, tau=8) > 0.9


def test_tau_zero_reacts_to_most_recent():
    """T-07-06: tau -> 0 makes momentum track only the most recent event."""
    events = [_event("AWAY", 5, "shot"), _event("HOME", 40, "shot")]
    m = momentum_index(events, current_minute=40, tau=0.01)
    assert m > 0.99  # dominated by the most recent (HOME) event


def test_tau_infinite_is_count_ratio():
    """T-07-07: tau -> infinity converges to the unweighted count ratio."""
    events = [_event("HOME", 10, "shot"), _event("HOME", 20, "shot"),
              _event("HOME", 30, "shot"), _event("AWAY", 15, "shot")]
    m = momentum_index(events, current_minute=90, tau=1e9)
    assert abs(m - 0.75) < 0.01


def test_future_events_ignored():
    """T-07-08: events after current_minute are ignored (mini-leakage check)."""
    base = [_event("HOME", 20, "shot")]
    future = base + [_event("HOME", 80, "shot_on_target")]
    p_base = offensive_pressure(base, "HOME", 30, 8)
    p_future = offensive_pressure(future, "HOME", 30, 8)
    assert p_base == p_future
