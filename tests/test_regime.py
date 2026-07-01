"""C.9 — Regime detector (Section 9)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from fie.events import Event, State
from fie.prediction import Params
from fie.regime import REGIMES, detect_regime
from tests.generators import regime_scenarios

SC = regime_scenarios()


def _check(name):
    s = SC[name]
    assert detect_regime(s["state"], s["events"], s["params"]) == s["expected"]


def test_post_goal():
    """T-09-01: a goal 2 minutes ago -> POST_GOAL."""
    _check("POST_GOAL")


def test_post_red_card():
    """T-09-02: a red card with no other trigger active -> POST_RED_CARD."""
    _check("POST_RED_CARD")


def test_end_game():
    """T-09-03: minute 85, score tied -> END_GAME."""
    _check("END_GAME")


def test_desperation():
    """T-09-04: minute 85, score not tied -> DESPERATION."""
    _check("DESPERATION")


def test_pressure():
    """T-09-05: minute 40, one team's momentum > threshold -> PRESSURE."""
    _check("PRESSURE")


def test_normal():
    """T-09-06: minute 40, balanced momentum -> NORMAL."""
    _check("NORMAL")


def test_priority_post_goal_wins_late():
    """T-09-08: a post-goal state at minute 86 still returns POST_GOAL."""
    _check("POST_GOAL_LATE")


event_strategy = st.builds(
    lambda team, minute, etype: Event(match_id="t", minute=float(minute), team=team, type=etype),
    st.sampled_from(["HOME", "AWAY"]),
    st.floats(min_value=0, max_value=90),
    st.sampled_from(["shot", "shot_on_target", "goal", "red_card", "corner"]),
)


@given(
    minute=st.floats(min_value=0, max_value=95),
    hg=st.integers(min_value=0, max_value=5),
    ag=st.integers(min_value=0, max_value=5),
    events=st.lists(event_strategy, max_size=30),
)
@settings(max_examples=500)
def test_regime_always_known(minute, hg, ag, events):
    """T-09-07: detect_regime always returns one of the six known labels."""
    state = State(minute=minute, home_goals=hg, away_goals=ag)
    assert detect_regime(state, events, Params()) in REGIMES
