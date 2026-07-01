"""Change detector — Temporal Intelligence (Section 11).

Answers one question: did the game just change? Before kick-off, history sets an
expectation; minutes later reality can contradict it. The change score measures
that distance, in ``[0, 100]``.
"""

from __future__ import annotations

from .indices import momentum_index


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def change_score(expected_home_strength: float, state, events, params) -> int:
    """Distance between the observed picture and the pre-match expectation."""
    control = momentum_index(events, state.minute, params.tau)
    dev_control = abs(control - expected_home_strength)

    lead = _sign(state.home_goals - state.away_goals)
    expected = _sign(expected_home_strength - 0.5)
    if lead == expected:
        dev_lead = 0.0
    elif lead == 0 or expected == 0:
        dev_lead = 0.5
    else:
        dev_lead = 1.0

    raw = 0.6 * dev_control + 0.4 * dev_lead
    return round(100 * min(1.0, 1.25 * raw))
