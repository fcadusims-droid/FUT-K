"""Continuous learning (Section 21).

Stage 2: instead of guessing parameters, tune them to minimize log loss over
historical data — always with a walk-forward split so we measure insight, not
overfitting.
"""

from __future__ import annotations

from dataclasses import replace

from .calibration import backtest, log_loss

# Default search grid for the base rate (goals/min per team).
DEFAULT_BASE_RATE_GRID = (0.008, 0.010, 0.012, 0.015, 0.018, 0.020, 0.025, 0.030)


def training_cost(matches, params) -> float:
    """Log loss of ``params`` over ``matches`` via a leakage-safe backtest."""
    result = backtest(matches, params)
    return log_loss(result["pairs"])


def fit_parameters(train_matches, params0, grid=DEFAULT_BASE_RATE_GRID):
    """Tune ``base_rate`` to minimize training log loss (Stage 2).

    A deliberately simple 1-D search — enough to demonstrate that fitting reduces
    training loss (T-21-01) and can also help out of sample (T-21-02), while a
    small/noisy training set can overfit and hurt held-out loss (T-21-03).
    """
    best = params0
    best_cost = training_cost(train_matches, params0)
    for br in grid:
        candidate = replace(params0, base_rate=br)
        cost = training_cost(train_matches, candidate)
        if cost < best_cost:
            best_cost = cost
            best = candidate
    return best


def walk_forward_split(items, n_folds: int = 3, key=lambda x: x):
    """Yield ``(train, test)`` folds where every train window strictly precedes
    its test window in time (T-21-04).

    ``items`` are sorted by ``key`` (a time-like ordering). Each fold uses an
    expanding training window and the next contiguous block as the test window.
    """
    ordered = sorted(items, key=key)
    n = len(ordered)
    if n_folds < 1 or n < n_folds + 1:
        return
    block = n // (n_folds + 1)
    if block == 0:
        return
    for i in range(1, n_folds + 1):
        train = ordered[: i * block]
        test = ordered[i * block : (i + 1) * block]
        if train and test:
            yield train, test
