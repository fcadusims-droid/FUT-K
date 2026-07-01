"""Regime detector — Contextual Intelligence (Section 9).

Football is not stationary: it changes state, and the same numbers mean different
things in different states. The regime reconditions the multipliers of Section 8
and the reading of the indices of Section 7.
"""

from __future__ import annotations

from .indices import momentum_index

# The six regimes (Section 9.1).
REGIMES = {
    "NORMAL",
    "PRESSURE",
    "DESPERATION",
    "POST_GOAL",
    "POST_RED_CARD",
    "END_GAME",
}

# How long, in minutes, a goal / red card keeps the match in its "post-" regime.
POST_GOAL_WINDOW = 5.0
POST_RED_CARD_WINDOW = 10.0


def minutes_since_last_goal(events, minute: float) -> float:
    """Minutes since the most recent goal at or before ``minute`` (inf if none)."""
    goals = [e.minute for e in events if e.type == "goal" and e.minute <= minute]
    return (minute - max(goals)) if goals else float("inf")


def red_card_happened(events, minute: float, window: float = POST_RED_CARD_WINDOW) -> bool:
    """True if a red card was shown within ``window`` minutes up to ``minute``."""
    return any(
        e.type == "red_card" and 0 <= minute - e.minute <= window for e in events
    )


def detect_regime(state, events, params) -> str:
    """Classify the current regime. Priority order matters (see T-09-08)."""
    if minutes_since_last_goal(events, state.minute) < POST_GOAL_WINDOW:
        return "POST_GOAL"
    if red_card_happened(events, state.minute):
        return "POST_RED_CARD"
    if state.minute > 80:
        return "DESPERATION" if state.home_goals != state.away_goals else "END_GAME"
    mom = momentum_index(events, state.minute, params.tau)
    if max(mom, 1 - mom) > params.pressure_threshold:
        return "PRESSURE"
    return "NORMAL"


def regime_instability(prev_regime, regime) -> float:
    """1.0 the moment the regime changes, else 0.0.

    Regime transitions are moments of instability that should lower confidence
    (Section 10). This is the discrete signal a temporal tracker would smooth.
    """
    if prev_regime is None:
        return 0.0
    return 1.0 if prev_regime != regime else 0.0
