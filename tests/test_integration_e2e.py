"""C.22 — Integration / end-to-end tests (Section 22)."""

from __future__ import annotations

import pytest

from fie.confidence import confidence
from fie.events import Event, state_from_events
from fie.indices import momentum_index
from fie.memory import remember, replay
from fie.prediction import Params, predictions
from fie.regime import REGIMES, detect_regime, regime_instability
from tests.conftest import SEED, SEEDS3
from tests.generators import league_simulator, poisson_match


def _story_events():
    """Hand-built match script: NORMAL -> PRESSURE -> POST_GOAL -> END_GAME."""
    events = [
        Event("arc", 10, "HOME", "shot"),
        Event("arc", 12, "AWAY", "shot"),
    ]
    events += [Event("arc", m, "HOME", "shot_on_target") for m in (35, 36, 37, 38, 39)]
    events += [
        Event("arc", 44, "HOME", "goal"),
        Event("arc", 60, "AWAY", "goal"),
    ]
    return events


def test_pipeline_runs_and_stays_bounded():
    """T-INT-01: the full pipeline runs end-to-end with every output in bounds."""
    match = poisson_match(0.02, 0.02, seed=SEED, match_id="e2e")
    events = list(match["events"])
    events += [
        Event("e2e", m, "HOME" if i % 2 else "AWAY", "shot")
        for i, m in enumerate(range(6, 88, 6))
    ]
    events.sort(key=lambda e: e.minute)
    params = Params()

    prev_regime = None
    for minute in range(5, 86, 5):
        events_until = [e for e in events if e.minute <= minute]
        state = state_from_events("e2e", events, minute)

        mom = momentum_index(events_until, minute, params.tau)
        regime = detect_regime(state, events_until, params)
        preds = predictions(state, events_until, params, regime=regime)
        conf = confidence(
            n_events=len(events_until), source_quality=0.9, source_agreement=0.8,
            regime_instability=regime_instability(prev_regime, regime), similar_cases=30,
        )

        assert 0.0 <= mom <= 1.0
        assert regime in REGIMES
        assert 0.0 <= conf <= 1.0
        for key in ("goal_next_5min", "goal_next_10min", "goal_before_half"):
            assert 0.0 <= preds[key] <= 1.0
        assert abs(preds["next_goal"]["HOME"] + preds["next_goal"]["AWAY"] - 1.0) < 1e-9
        prev_regime = regime


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_panel_aggregate_matches_generator(seed):
    """T-INT-02: aggregate goals/match over 1000 matches match the generator."""
    matches = league_simulator(1000, base_rate=0.015, seed=seed)
    expected = sum((m["lambda_home"] + m["lambda_away"]) * m["duration"] for m in matches)
    observed = sum(m["home_goals"] + m["away_goals"] for m in matches)
    assert abs(observed - expected) / expected < 0.03


def test_story_arc_regime_sequence_and_timeline():
    """T-INT-03: a story-arc match yields the expected regime sequence + timeline."""
    events = _story_events()
    params = Params()
    checkpoints = [
        (20, "NORMAL"),
        (40, "PRESSURE"),
        (46, "POST_GOAL"),
        (85, "END_GAME"),
    ]

    timeline = []
    observed_sequence = []
    for minute, _ in checkpoints:
        events_until = [e for e in events if e.minute <= minute]
        state = state_from_events("arc", events, minute)
        regime = detect_regime(state, events_until, params)
        observed_sequence.append(regime)
        remember(timeline, minute, regime)

    assert observed_sequence == [label for _, label in checkpoints]

    replayed = replay(timeline)
    minutes = [e["minute"] for e in replayed]
    assert minutes == sorted(minutes)
    assert all(b > a for a, b in zip(minutes, minutes[1:]))  # strictly increasing
