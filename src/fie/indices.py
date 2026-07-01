"""Index engine — State & Spatial Intelligence (Section 7).

Turns thousands of events into a few interpretable numbers. The key refinement
over a naive "last 10 minutes" window is exponential decay: recent events weigh
more, smoothly, with no artificial cut-off.
"""

from __future__ import annotations

import math

# Offensive weight per event type (Section 7.2).
EVENT_WEIGHT = {
    "shot_on_target": 3.0,
    "shot": 1.5,
    "dangerous_attack": 1.0,
    "corner": 1.2,
}


def time_weight(current_minute: float, ev_minute: float, tau: float) -> float:
    """Exponential decay weight of an event (Section 7.1).

    ``time_weight = exp( -(current_minute - ev_minute) / tau )``.
    """
    return math.exp(-(current_minute - ev_minute) / tau)


def offensive_pressure(events, team: str, current_minute: float, tau: float) -> float:
    """Decay-weighted offensive pressure of ``team`` up to ``current_minute``."""
    total = 0.0
    for ev in events:
        if ev.team == team and ev.minute <= current_minute:
            w = EVENT_WEIGHT.get(ev.type, 0.0)
            if w:
                total += w * math.exp(-(current_minute - ev.minute) / tau)
    return total


def momentum_index(events, current_minute: float, tau: float) -> float:
    """Home's share of recent offensive pressure, in ``[0, 1]``.

    ``> 0.5`` means HOME is dominating the recent minutes. With no offensive
    events on either side the game is, by definition, balanced -> exactly ``0.5``.
    """
    ph = offensive_pressure(events, "HOME", current_minute, tau)
    pa = offensive_pressure(events, "AWAY", current_minute, tau)
    return 0.5 if ph + pa == 0 else ph / (ph + pa)


def control_index(events, current_minute: float, tau: float) -> float:
    """Territorial dominance proxy for HOME, approximated from relative attacks.

    Without possession data we approximate control by the decay-weighted share of
    attacking actions — the same substrate as momentum, exposed under its own
    name for the panel (Section 22).
    """
    return momentum_index(events, current_minute, tau)


def vulnerability_index(events, team: str, current_minute: float, tau: float) -> float:
    """Offensive pressure conceded by ``team`` (i.e. the opponent's pressure)."""
    opponent = "AWAY" if team == "HOME" else "HOME"
    return offensive_pressure(events, opponent, current_minute, tau)
