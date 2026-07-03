"""The intelligent panel (Section 22) as a pure function.

``panel_state(events, minute, ...)`` -> everything the frontend needs for one
minute of a match: score, regime, momentum, predictions with confidence, change
score, and the explained "why". Reuses only validated ``fie`` functions and is
leakage-safe by construction: it slices events at ``minute`` before computing
anything, so appending future events can never change a past panel.
"""

from __future__ import annotations

from fie.change import change_score
from fie.confidence import confidence as fie_confidence
from fie.events import Event, State, state_from_events
from fie.explain import explain
from fie.indices import momentum_index, offensive_pressure
from fie.prediction import Params, predictions
from fie.regime import detect_regime, regime_instability

# The panel reads a single curated source per replay (StatsBomb events), so it
# uses fixed trust factors here. The Section 16 consensus idea ships separately
# as the fusion layer (fie.fusion, per-match cross-check at /crosscheck);
# feeding a *live* multi-source consensus into the panel is the future step.
SOURCE_QUALITY = 0.95
SOURCE_AGREEMENT = 1.0
SIMILAR_CASES = 50  # historical DB is populated (Phase A3); refine in Phase D

REGIME_LOOKBACK = 5.0  # minutes back to detect a regime transition

# fie.regime.regime_instability is a discrete 0/1 signal whose docstring says a
# temporal tracker should smooth it. Feeding the raw 1.0 into the geometric-mean
# confidence would zero it on every transition; Section 10.1 asks for *low*
# confidence right after a regime change, not none. So a transition maps to this
# softened instability instead (f_regime = 0.4).
INSTABILITY_ON_TRANSITION = 0.6


def _row_to_event(row) -> Event:
    """Map an ORM events row to the engine's Event."""
    return Event(
        match_id=row.match_id, minute=row.minute, team=row.team, type=row.type,
        player_id=row.player_id, target_id=row.target_id, x=row.x, y=row.y, xg=row.xg,
    )


def _mechanisms(state: State, events_until, mom: float, params: Params) -> list:
    """Readable mechanism lines from simple, documented triggers."""
    lines = []
    dominant = "HOME" if mom >= 0.5 else "AWAY"
    share = max(mom, 1 - mom)
    if share > 0.65:
        lines.append(f"sustained pressure by {dominant} ({share:.0%} of recent momentum)")
    recent_shots = sum(
        1 for e in events_until
        if e.type in ("shot", "shot_on_target") and state.minute - e.minute <= 10
    )
    if recent_shots >= 3:
        lines.append(f"{recent_shots} shots in the last 10 minutes")
    diff = state.home_goals - state.away_goals
    if diff != 0 and state.minute > 75:
        trailing = "AWAY" if diff > 0 else "HOME"
        lines.append(f"{trailing} chasing the game late")
    return lines


def panel_state(
    events: list[Event],
    minute: float,
    match_id: str = "",
    params: Params | None = None,
    expected_home_strength: float = 0.5,
    window: float = 10.0,
) -> dict:
    """Compute the full Section 22 panel for one minute. Leakage-safe."""
    params = params or Params()
    events_until = [e for e in events if e.minute <= minute]
    state = state_from_events(match_id, events, minute)

    regime = detect_regime(state, events_until, params)
    prev_events = [e for e in events_until if e.minute <= minute - REGIME_LOOKBACK]
    prev_state = state_from_events(match_id, events, max(0.0, minute - REGIME_LOOKBACK))
    prev_regime = detect_regime(prev_state, prev_events, params) if minute >= REGIME_LOOKBACK else None
    instability = INSTABILITY_ON_TRANSITION * regime_instability(prev_regime, regime)

    mom = momentum_index(events_until, minute, params.tau)
    preds = predictions(state, events_until, params, regime=regime)
    conf = fie_confidence(
        n_events=len(events_until),
        source_quality=SOURCE_QUALITY,
        source_agreement=SOURCE_AGREEMENT,
        regime_instability=instability,
        similar_cases=SIMILAR_CASES,
    )
    change = change_score(expected_home_strength, state, events_until, params)

    mechanisms = _mechanisms(state, events_until, mom, params)
    change_note = {"minute": minute} if instability else None
    explanation = explain(
        prediction=f"goal in next {int(window)} min: {preds['goal_next_10min']:.0%}",
        change=change_note, causes=[], mechanisms=mechanisms, drivers=[],
        confidence=conf,
    )

    return {
        "match_id": match_id,
        "minute": minute,
        "score": {"home": state.home_goals, "away": state.away_goals},
        "regime": regime,
        "confidence": round(conf, 3),
        "change_score": change,
        "momentum": {"home": round(mom, 3), "away": round(1 - mom, 3)},
        "pressure": {
            "home": round(offensive_pressure(events_until, "HOME", minute, params.tau), 3),
            "away": round(offensive_pressure(events_until, "AWAY", minute, params.tau), 3),
        },
        "predictions": {
            "goal_next_5min": round(preds["goal_next_5min"], 3),
            "goal_next_10min": round(preds["goal_next_10min"], 3),
            "goal_before_half": round(preds["goal_before_half"], 3),
            "next_goal": {
                "home": round(preds["next_goal"]["HOME"], 3),
                "away": round(preds["next_goal"]["AWAY"], 3),
            },
        },
        "explanation": explanation,
    }
