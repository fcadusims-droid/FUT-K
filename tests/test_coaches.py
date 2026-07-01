"""C.13 — Coach Intelligence (Section 13)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fie.coaches import coach_adjustment, coaching_philosophy
from fie.events import State


def test_philosophy_not_mislabeled():
    """T-13-01: {winning: retreat, losing: press} falls to BALANCED per the rule.

    Catches a mismatch between prose and code: OFFENSIVE/PRAGMATIC each require a
    specific combination, and this one matches neither.
    """
    assert coaching_philosophy({"winning": "retreat", "losing": "press"}) == "BALANCED"


def test_philosophy_offensive():
    """T-13-02: {losing: press, winning: hold} -> OFFENSIVE."""
    assert coaching_philosophy({"losing": "press", "winning": "hold"}) == "OFFENSIVE"


def test_philosophy_pragmatic():
    """T-13-03: {losing: hold, winning: retreat} -> PRAGMATIC."""
    assert coaching_philosophy({"losing": "hold", "winning": "retreat"}) == "PRAGMATIC"


def test_coach_adjustment_cases():
    """T-13-04: 0.85 only when leading AND retreat; 1.20 when losing AND press."""
    leading = State(minute=70, home_goals=1, away_goals=0)
    losing = State(minute=70, home_goals=0, away_goals=1)
    drawing = State(minute=70, home_goals=1, away_goals=1)

    assert coach_adjustment(leading, "HOME", {"winning": "retreat"}) == 0.85
    assert coach_adjustment(losing, "HOME", {"losing": "press"}) == 1.20
    # Fall-throughs to 1.0:
    assert coach_adjustment(leading, "HOME", {"winning": "hold"}) == 1.0
    assert coach_adjustment(losing, "HOME", {"losing": "hold"}) == 1.0
    assert coach_adjustment(drawing, "HOME", {"winning": "retreat", "losing": "press"}) == 1.0
    # Leading but profile says press -> not 1.20 (wrong sign), not 0.85 -> 1.0
    assert coach_adjustment(leading, "HOME", {"losing": "press"}) == 1.0


@given(
    hg=st.integers(min_value=0, max_value=4),
    ag=st.integers(min_value=0, max_value=4),
    winning=st.sampled_from(["retreat", "hold", "press", None]),
    losing=st.sampled_from(["retreat", "hold", "press", None]),
    team=st.sampled_from(["HOME", "AWAY"]),
)
def test_coach_adjustment_three_valued(hg, ag, winning, losing, team):
    """T-13-05: coach_adjustment only ever returns one of {0.85, 1.0, 1.20}."""
    state = State(minute=70, home_goals=hg, away_goals=ag)
    profile = {"winning": winning, "losing": losing}
    assert coach_adjustment(state, team, profile) in {0.85, 1.0, 1.20}
