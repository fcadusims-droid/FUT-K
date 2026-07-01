"""Shared measurement routines for the Monte-Carlo experiments (Part C/F/G).

Each function returns an ``(observed, target, tolerance)`` triple for one of the
REGRESSION / MC reference numbers quoted in the design documents, so both
``report.py`` and ``run_monte_carlo.py`` compute identical values.
"""

from __future__ import annotations

import os
import sys

# Make ``tests/generators`` importable when run as a plain script.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_ROOT, "tests") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "tests"))

import numpy as np  # noqa: E402

from fie.calibration import brier, max_reliability_deviation  # noqa: E402
from fie.narrative import update_credibility, update_narrative_memory  # noqa: E402
from fie.prediction import BASE_RATE, prob_event_within  # noqa: E402
from generators import (  # noqa: E402
    goal_window_snapshots,
    narrative_pattern_world,
    narrative_world,
    simulate_goal_in_window,
    simulate_goals_per_match,
)

SEED = 20240607


def exp_goal_window(n=100_000):
    """T-08-03 — goal-in-window formula vs simulated frequency."""
    formula = prob_event_within(2 * BASE_RATE, 10)
    empirical = simulate_goal_in_window(BASE_RATE, BASE_RATE, 10, n=n, seed=SEED)
    return empirical, formula, 0.005


def exp_goals_per_match(n=80_000):
    """T-08-06 — base rate reproduces ~2.7 goals/match."""
    observed = simulate_goals_per_match(BASE_RATE, BASE_RATE, 90, n=n, seed=SEED)
    return observed, 2.7, 0.1


def exp_brier_calibrated(n=200_000):
    """T-20-01 — Brier of a perfectly calibrated predictor."""
    _, p_true, outcomes = goal_window_snapshots(n=n, seed=SEED, lam_low=0.03, lam_high=0.03)
    return brier(list(zip(p_true, outcomes))), 0.190, 0.01


def exp_brier_biased(n=200_000):
    """T-20-02 — biased predictor scores a worse Brier on the same outcomes."""
    lam, _, outcomes = goal_window_snapshots(n=n, seed=SEED, lam_low=0.03, lam_high=0.03)
    p_biased = 1.0 - np.exp(-1.4 * lam * 10)
    return brier(list(zip(p_biased, outcomes))), 0.199, 0.01


def exp_reliability_deviation(n=400_000):
    """T-20-03 — max deviation from the diagonal for a calibrated predictor."""
    _, p_true, outcomes = goal_window_snapshots(n=n, seed=SEED, lam_low=0.02, lam_high=0.06)
    return max_reliability_deviation(list(zip(p_true, outcomes)), n_bands=10), 0.0012, 0.01


def exp_credibility_convergence(n=20_000):
    """T-15-04 — source credibility converges to its true hit rate (0.70)."""
    labels = narrative_world(true_accuracy=0.70, n_opinions=n, seed=SEED)
    source = {}
    for label in labels:
        update_credibility(source, label)
    return source["weight"], 0.70, 0.02


def exp_narrative_memory(n=5_000):
    """T-15-09 — a recurring cliché's reliability converges to its true rate (0.18)."""
    draws = narrative_pattern_world(true_rate=0.18, n_games=n, seed=SEED)
    memory = {}
    for confirmed in draws:
        update_narrative_memory(memory, "team_X_collapses_late", confirmed)
    return memory["team_X_collapses_late"]["rate"], 0.18, 0.02


# (test_id, module, type, function)
EXPERIMENTS = [
    ("T-08-03", "prediction.py", "MC", exp_goal_window),
    ("T-08-06", "prediction.py", "REGRESSION", exp_goals_per_match),
    ("T-20-01", "calibration.py", "REGRESSION", exp_brier_calibrated),
    ("T-20-02", "calibration.py", "MUTATION", exp_brier_biased),
    ("T-20-03", "calibration.py", "FORMULA", exp_reliability_deviation),
    ("T-15-04", "narrative.py", "CONVERGENCE", exp_credibility_convergence),
    ("T-15-09", "narrative.py", "CONVERGENCE", exp_narrative_memory),
]


def run_all():
    """Return a list of result dicts for every experiment."""
    rows = []
    for test_id, module, kind, fn in EXPERIMENTS:
        observed, target, tol = fn()
        rows.append(
            {
                "id": test_id,
                "module": module,
                "type": kind,
                "observed": observed,
                "target": target,
                "tolerance": tol,
                "status": "PASS" if abs(observed - target) <= tol else "FAIL",
            }
        )
    return rows
