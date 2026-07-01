"""Poisson match generator + vectorized Monte-Carlo helpers (Part D.1).

``poisson_match`` builds one synthetic match as goal-only events drawn from two
independent Poisson processes. The ``simulate_*`` helpers are vectorized numpy
routines that run the same generating process at scale for the MC tests, without
allocating millions of Event objects.
"""

from __future__ import annotations

import numpy as np

from fie.events import Event


def _rate_segments(lam, duration, injections):
    """Piecewise-constant intensity segments ``(start, end, rate)``.

    ``injections`` is a list of ``(minute, multiplier)`` — from ``minute`` the
    intensity becomes ``lam * multiplier``. This models regime changes (e.g. a
    lambda jump after a red card at minute 60).
    """
    breaks = sorted(injections or [], key=lambda x: x[0])
    segments = []
    prev_min = 0.0
    mult = 1.0
    for minute, new_mult in breaks:
        minute = min(minute, duration)
        if minute > prev_min:
            segments.append((prev_min, minute, lam * mult))
        mult = new_mult
        prev_min = minute
    if prev_min < duration:
        segments.append((prev_min, duration, lam * mult))
    return segments


def _simulate_process(lam, duration, injections, rng):
    """Goal times for one piecewise-homogeneous Poisson process."""
    times = []
    for start, end, rate in _rate_segments(lam, duration, injections):
        if rate <= 0:
            continue
        t = start
        while True:
            t += rng.exponential(1.0 / rate)
            if t >= end:
                break
            times.append(t)
    return times


def poisson_match(
    lambda_home,
    lambda_away,
    duration=90,
    seed=None,
    injections=None,
    match_id="sim",
):
    """One synthetic match as a list of goal events + the final score."""
    rng = np.random.default_rng(seed)
    events = []
    home_times = _simulate_process(lambda_home, duration, injections, rng)
    away_times = _simulate_process(lambda_away, duration, injections, rng)
    for t in home_times:
        events.append(Event(match_id=match_id, minute=float(t), team="HOME", type="goal"))
    for t in away_times:
        events.append(Event(match_id=match_id, minute=float(t), team="AWAY", type="goal"))
    events.sort(key=lambda e: e.minute)
    return {
        "match_id": match_id,
        "events": events,
        "duration": duration,
        "home_goals": len(home_times),
        "away_goals": len(away_times),
    }


# --------------------------------------------------------------------------- #
# Vectorized Monte-Carlo helpers (same generating process, run at scale)
# --------------------------------------------------------------------------- #
def _first_time(lam, n, rng):
    """Time to the first event of a rate-``lam`` Poisson process (inf if lam=0)."""
    if lam <= 0:
        return np.full(n, np.inf)
    return rng.exponential(1.0 / lam, n)


def simulate_goal_in_window(lambda_home, lambda_away, window, n, seed=None):
    """Empirical fraction of matches with >=1 goal in the first ``window`` min."""
    rng = np.random.default_rng(seed)
    first = np.minimum(_first_time(lambda_home, n, rng), _first_time(lambda_away, n, rng))
    return float(np.mean(first <= window))


def simulate_first_scorer(lambda_home, lambda_away, n, seed=None):
    """Empirical share of "HOME scored first", conditional on a goal existing."""
    rng = np.random.default_rng(seed)
    th = _first_time(lambda_home, n, rng)
    ta = _first_time(lambda_away, n, rng)
    scored = np.isfinite(np.minimum(th, ta))
    home_first = (th < ta) & scored
    return float(np.sum(home_first) / np.sum(scored))


def simulate_goals_per_match(lambda_home, lambda_away, duration, n, seed=None):
    """Empirical mean total goals per match."""
    rng = np.random.default_rng(seed)
    gh = rng.poisson(lambda_home * duration, n)
    ga = rng.poisson(lambda_away * duration, n)
    return float(np.mean(gh + ga))


def simulate_on_off_influence(base_lambda, k, on_minutes, off_minutes, n_matches, seed=None):
    """Estimate ``(lambda_on, lambda_off)`` for a player whose presence scales the
    team's rate by ``k``. The recovered factor ``lambda_on / lambda_off`` should
    approach ``k`` (T-12-05)."""
    rng = np.random.default_rng(seed)
    on_goals = rng.poisson(base_lambda * k * on_minutes, n_matches).sum()
    off_goals = rng.poisson(base_lambda * off_minutes, n_matches).sum()
    lambda_on = on_goals / (n_matches * on_minutes)
    lambda_off = off_goals / (n_matches * off_minutes)
    return float(lambda_on), float(lambda_off)


def goal_window_snapshots(n, window=10, seed=None, lam_low=0.03, lam_high=0.03):
    """Snapshots for calibration tests.

    Returns ``(lam_total, p_true, outcomes)``: per-snapshot total intensity, the
    true "goal within window" probability, and a Bernoulli(p_true) outcome. When
    ``lam_low == lam_high`` every snapshot shares the same true probability.
    """
    rng = np.random.default_rng(seed)
    lam = rng.uniform(lam_low, lam_high, n)
    p_true = 1.0 - np.exp(-lam * window)
    outcomes = (rng.random(n) < p_true).astype(int)
    return lam, p_true, outcomes
