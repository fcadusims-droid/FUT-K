"""Hand-built regime fixtures (Part D.4).

One named scenario per regime label, kept in one place so a change to the regime
rules only requires updating fixtures once. Each scenario carries the ``state``,
the ``events``, the ``params`` and the ``expected`` regime label.
"""

from __future__ import annotations

from fie.events import Event, State
from fie.prediction import Params

_PARAMS = Params()


def _shots(team, minutes, match_id="reg"):
    return [Event(match_id=match_id, minute=float(m), team=team, type="shot_on_target")
            for m in minutes]


def regime_scenarios():
    """Return ``{name: {state, events, params, expected}}`` for every regime."""
    scenarios = {}

    # NORMAL — minute 40, balanced pressure.
    scenarios["NORMAL"] = {
        "state": State(minute=40, home_goals=0, away_goals=0),
        "events": _shots("HOME", [36, 38]) + _shots("AWAY", [37, 39]),
        "params": _PARAMS,
        "expected": "NORMAL",
    }

    # PRESSURE — minute 40, HOME stacking attacks, AWAY silent.
    scenarios["PRESSURE"] = {
        "state": State(minute=40, home_goals=0, away_goals=0),
        "events": _shots("HOME", [35, 36, 37, 38, 39, 39.5]),
        "params": _PARAMS,
        "expected": "PRESSURE",
    }

    # POST_GOAL — a goal two minutes ago.
    scenarios["POST_GOAL"] = {
        "state": State(minute=44, home_goals=1, away_goals=0),
        "events": [Event(match_id="reg", minute=42, team="HOME", type="goal")],
        "params": _PARAMS,
        "expected": "POST_GOAL",
    }

    # POST_RED_CARD — a red card a few minutes ago, no other trigger active.
    scenarios["POST_RED_CARD"] = {
        "state": State(minute=52, home_goals=0, away_goals=0),
        "events": [Event(match_id="reg", minute=50, team="AWAY", type="red_card")],
        "params": _PARAMS,
        "expected": "POST_RED_CARD",
    }

    # END_GAME — minute 85, level.
    scenarios["END_GAME"] = {
        "state": State(minute=85, home_goals=1, away_goals=1),
        "events": _shots("HOME", [70]) + _shots("AWAY", [72]),
        "params": _PARAMS,
        "expected": "END_GAME",
    }

    # DESPERATION — minute 85, one side chasing.
    scenarios["DESPERATION"] = {
        "state": State(minute=85, home_goals=0, away_goals=1),
        "events": _shots("HOME", [70]) + _shots("AWAY", [72]),
        "params": _PARAMS,
        "expected": "DESPERATION",
    }

    # POST_GOAL_LATE — overlapping triggers: a goal at 85 must still win at 86.
    scenarios["POST_GOAL_LATE"] = {
        "state": State(minute=86, home_goals=1, away_goals=0),
        "events": [Event(match_id="reg", minute=85, team="HOME", type="goal")],
        "params": _PARAMS,
        "expected": "POST_GOAL",
    }

    return scenarios
