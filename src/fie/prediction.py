"""Prediction engine — Predictive Intelligence (Section 8).

Goals (and other events) are modelled as a Poisson process with a variable
intensity ``lambda`` that depends on the game state. From this one idea a whole
family of predictions follows with closed-form formulas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .indices import momentum_index

# Calibrated base rate: ~0.015 goals/min per team reproduces ~2.7 goals/match in a
# neutral scenario (Section 8.2, validated by T-08-06).
BASE_RATE = 0.015


@dataclass
class Params:
    """Tunable parameters of the engine (learned in Section 21)."""

    base_rate: float = BASE_RATE
    tau: float = 8.0
    pressure_threshold: float = 0.65
    regime_scale: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Closed-form Poisson formulas (Section 8.1 / 8.3)
# --------------------------------------------------------------------------- #
def poisson_at_least(lmbda: float, k: int) -> float:
    """``P(at least k events)`` for a Poisson variable with mean ``lmbda``."""
    if k <= 0:
        return 1.0
    cdf = sum(math.exp(-lmbda) * lmbda ** i / math.factorial(i) for i in range(k))
    return max(0.0, 1.0 - cdf)


def prob_event_within(lambda_event: float, minutes: float) -> float:
    """``P(at least one event in `minutes`)`` for rate ``lambda_event``/min."""
    return 1 - math.exp(-lambda_event * minutes)


def prob_next_goal(lam_home: float, lam_away: float) -> dict:
    """Probability that the next goal belongs to each side."""
    s = lam_home + lam_away
    if s == 0:
        return {"HOME": 0.5, "AWAY": 0.5}
    return {"HOME": lam_home / s, "AWAY": lam_away / s}


# --------------------------------------------------------------------------- #
# Dynamic intensity multipliers (Section 8.2)
#
# Each multiplier is documented and bounded so that lambda can never go negative
# (T-08-07). The multipliers here are the ones that are *always available*; the
# player-aware `mult_lineup` factor is layered on top in players.py and is 1
# (neutral) without player data.
# --------------------------------------------------------------------------- #
def mult_pressure(events, team: str, minute: float, params: Params) -> float:
    """How much ``team`` is pressing now. Maps momentum share to ``[0.5, 1.5]``."""
    mom = momentum_index(events, minute, params.tau)
    share = mom if team == "HOME" else 1.0 - mom
    return 0.5 + share


def mult_score(state, team: str, profile=None) -> float:
    """Score effect. Coach-specific when a profile is given (Section 13)."""
    if profile is not None:
        # Imported lazily to keep this module importable on its own.
        from .coaches import coach_adjustment

        return coach_adjustment(state, team, profile)
    diff = state.goal_diff(team)
    if diff > 0:
        return 0.9  # a leading team often retreats
    if diff < 0:
        return 1.1  # a trailing team pushes
    return 1.0


def mult_time(minute: float) -> float:
    """Goals cluster near the end of each half. Bounded to ``[1.0, 1.4]``."""
    d = min(abs(minute - 45.0), abs(minute - 90.0))
    return 1.0 + 0.4 * math.exp(-d / 6.0)


def mult_card(events, team: str, minute: float) -> float:
    """Sendings-off: opponent red cards help ``team``, own red cards hurt it."""
    opponent = "AWAY" if team == "HOME" else "HOME"
    own_red = sum(
        1 for e in events if e.type == "red_card" and e.team == team and e.minute <= minute
    )
    opp_red = sum(
        1 for e in events if e.type == "red_card" and e.team == opponent and e.minute <= minute
    )
    return max(0.0, 1.0 + 0.20 * opp_red) * max(0.0, 1.0 - 0.15 * own_red)


def rates(state, events, params: Params, regime=None, profiles=None):
    """Return ``(lambda_home, lambda_away)`` per minute, with all multipliers.

    Applies only the always-available multipliers. The ``mult_lineup`` factor
    (who is on the pitch) is layered on top by ``players.player_aware_lambda``
    when player data exists; without it, it is 1 (neutral).
    """
    rs = params.regime_scale.get(regime, 1.0) if regime else 1.0
    profiles = profiles or {}

    def lam(team):
        m = (
            mult_pressure(events, team, state.minute, params)
            * mult_score(state, team, profiles.get(team))
            * mult_time(state.minute)
            * mult_card(events, team, state.minute)
        )
        return params.base_rate * rs * m

    return lam("HOME"), lam("AWAY")


def predictions(state, events, params: Params, regime=None, profiles=None) -> dict:
    """The concrete next-development predictions read from the current state."""
    lam_home, lam_away = rates(state, events, params, regime, profiles)
    lam = lam_home + lam_away
    minutes_to_half = max(0.0, (45.0 if state.minute < 45 else 90.0) - state.minute)
    return {
        "goal_next_5min": prob_event_within(lam, 5),
        "goal_next_10min": prob_event_within(lam, 10),
        "goal_before_half": prob_event_within(lam, minutes_to_half),
        "next_goal": prob_next_goal(lam_home, lam_away),
        "lambda_home": lam_home,
        "lambda_away": lam_away,
    }
