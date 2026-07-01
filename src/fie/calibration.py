"""Validation and calibration (Section 20).

The most important part: without it we do not know whether we have a system or an
illusion. Calibration answers "when the model says 60%, does it happen 60% of the
time?"; ``backtest`` replays matches minute by minute with a hard no-leakage rule.
"""

from __future__ import annotations

import math

from .events import state_from_events
from .prediction import prob_event_within, rates
from .regime import detect_regime


def brier(pairs) -> float:
    """Brier score: ``mean((predicted - outcome)**2)``. Lower is better."""
    if not pairs:
        raise ValueError("brier() requires at least one (pred, outcome) pair")
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def log_loss(pairs, eps: float = 1e-15) -> float:
    """Log loss: ``-mean(y*ln(p) + (1-y)*ln(1-p))``. Punishes confident errors."""
    if not pairs:
        raise ValueError("log_loss() requires at least one (pred, outcome) pair")
    total = 0.0
    for p, o in pairs:
        p = min(1.0 - eps, max(eps, p))
        total += -(o * math.log(p) + (1 - o) * math.log(1 - p))
    return total / len(pairs)


def reliability_curve(pairs, n_bands: int = 10):
    """Bucket predictions into bands and compare mean predicted vs real frequency.

    Returns ``[(mean_predicted, observed_frequency, count), ...]`` for non-empty
    bands. A perfectly calibrated model lies on the diagonal ``y = x``.
    """
    bands = [[0, 0.0, 0.0] for _ in range(n_bands)]  # n, sum_pred, sum_happened
    for p, happened in pairs:
        i = min(n_bands - 1, int(p * n_bands))
        bands[i][0] += 1
        bands[i][1] += p
        bands[i][2] += happened
    return [(sp / n, so / n, n) for n, sp, so in bands if n > 0]


def max_reliability_deviation(pairs, n_bands: int = 10) -> float:
    """Maximum absolute deviation from the diagonal across populated bands."""
    curve = reliability_curve(pairs, n_bands)
    if not curve:
        return 0.0
    return max(abs(pred - obs) for pred, obs, _ in curve)


# --------------------------------------------------------------------------- #
# Backtesting without leakage (Section 20.2)
# --------------------------------------------------------------------------- #
def _goal_within(events, start: float, end: float) -> int:
    """1 if any goal occurred in ``(start, end]`` — an *outcome* (post-match)."""
    return 1 if any(e.type == "goal" and start < e.minute <= end for e in events) else 0


def predict_goal_within(state, events_until, params, window: float, regime=None) -> float:
    """Prediction for "a goal in the next ``window`` minutes" from the state.

    Uses only ``events_until`` — events at or before ``state.minute``. This is the
    single point where the leakage discipline lives.
    """
    if regime is None:
        regime = detect_regime(state, events_until, params)
    lam_home, lam_away = rates(state, events_until, params, regime=regime)
    return prob_event_within(lam_home + lam_away, window)


def backtest(matches, params, window: float = 10.0, eval_step: int = 5) -> dict:
    """Replay each match minute by minute, predicting with past-only information.

    ``matches`` is a list of dicts::

        {"match_id": str, "events": [Event, ...], "duration": 90,
         "eval_minutes": [5, 10, ...]}   # eval_minutes optional

    Returns ``{"pairs": [(prob, outcome), ...], "predictions": [...],
    "brier": float}``. Predictions depend only on events up to each minute;
    outcomes are resolved afterwards from the full event list.
    """
    pairs = []
    records = []
    for match in matches:
        match_id = match.get("match_id", "")
        all_events = sorted(match["events"], key=lambda e: e.minute)
        duration = int(match.get("duration", 90))
        eval_minutes = match.get("eval_minutes")
        if eval_minutes is None:
            last = max(eval_step, duration - int(window))
            eval_minutes = list(range(eval_step, last + 1, eval_step))
        for t in eval_minutes:
            # Leakage-safe slice: strictly events at or before minute t.
            events_until = [e for e in all_events if e.minute <= t]
            state = state_from_events(match_id, all_events, t)
            prob = predict_goal_within(state, events_until, params, window)
            happened = _goal_within(all_events, t, t + window)
            pairs.append((prob, happened))
            records.append(
                {
                    "match_id": match_id,
                    "minute": t,
                    "target": f"goal_{int(window)}min",
                    "prob": prob,
                }
            )
    result = {"pairs": pairs, "predictions": records}
    result["brier"] = brier(pairs) if pairs else float("nan")
    return result
