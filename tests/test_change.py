"""C.11 — Change detector (Section 11)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from fie.change import change_score
from fie.events import Event, State
from fie.prediction import Params

P = Params()


def _shots(team, minutes):
    return [Event(match_id="c", minute=float(m), team=team, type="shot_on_target")
            for m in minutes]


def test_underdog_dominating_and_leading():
    """T-11-01: underdog dominating control AND leading -> high change score."""
    events = _shots("AWAY", [80, 82, 84, 86, 88])  # away (underdog) controls
    state = State(minute=88, home_goals=0, away_goals=1)  # and leads
    score = change_score(expected_home_strength=0.8, state=state, events=events, params=P)
    assert score > 70


def test_favorite_as_expected():
    """T-11-02: favorite controlling and leading, as expected -> low change score."""
    events = _shots("HOME", [80, 82, 84, 86, 88])
    state = State(minute=88, home_goals=1, away_goals=0)
    score = change_score(expected_home_strength=0.9, state=state, events=events, params=P)
    assert score < 15


def test_balanced_expected_draw():
    """T-11-03: balanced game, expected draw -> near-zero change score."""
    events = _shots("HOME", [84, 88]) + _shots("AWAY", [84, 88])
    state = State(minute=88, home_goals=1, away_goals=1)
    score = change_score(expected_home_strength=0.5, state=state, events=events, params=P)
    assert score < 10


event_strategy = st.builds(
    lambda team, minute: Event(match_id="c", minute=float(minute), team=team, type="shot"),
    st.sampled_from(["HOME", "AWAY"]),
    st.floats(min_value=0, max_value=90),
)


@given(
    expected=st.floats(min_value=0, max_value=1),
    minute=st.floats(min_value=1, max_value=90),
    hg=st.integers(min_value=0, max_value=5),
    ag=st.integers(min_value=0, max_value=5),
    events=st.lists(event_strategy, max_size=20),
)
@settings(max_examples=500)
def test_change_score_bounded(expected, minute, hg, ag, events):
    """T-11-04: output always in [0, 100]."""
    state = State(minute=minute, home_goals=hg, away_goals=ag)
    score = change_score(expected, state, events, P)
    assert 0 <= score <= 100


def test_change_score_home_away_symmetry():
    """T-11-05: scores are equal under a full home/away mirror."""
    events = _shots("HOME", [80, 84, 88]) + _shots("AWAY", [86])
    state = State(minute=88, home_goals=2, away_goals=0)
    original = change_score(0.7, state, events, P)

    # Mirror: swap teams in events, swap goals, and reflect the expectation.
    swapped_events = [
        Event(match_id="c", minute=e.minute,
              team=("AWAY" if e.team == "HOME" else "HOME"), type=e.type)
        for e in events
    ]
    swapped_state = State(minute=88, home_goals=0, away_goals=2)
    mirrored = change_score(0.3, swapped_state, swapped_events, P)

    assert original == mirrored
