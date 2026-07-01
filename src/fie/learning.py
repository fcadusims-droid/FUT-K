"""Continuous learning (Section 21).

Stage 2: instead of guessing parameters, tune them to minimize log loss over
historical data — always with a walk-forward split so we measure insight, not
overfitting. Fitting searches ``base_rate`` (the overall goal-rate level) and,
optionally, ``tau`` (how fast pressure decays), the two constants that set how
aggressive the "goal soon" probabilities are.
"""

from __future__ import annotations

from dataclasses import replace

from .calibration import backtest, brier, log_loss, reliability_curve

# Default search grids.
DEFAULT_BASE_RATE_GRID = (0.008, 0.010, 0.012, 0.015, 0.018, 0.020, 0.025, 0.030)
DEFAULT_TAU_GRID = (4.0, 6.0, 8.0, 12.0, 16.0)


def training_cost(matches, params, window: float = 10.0) -> float:
    """Log loss of ``params`` over ``matches`` via a leakage-safe backtest."""
    result = backtest(matches, params, window=window)
    return log_loss(result["pairs"])


def fit_parameters(
    train_matches,
    params0,
    base_rate_grid=DEFAULT_BASE_RATE_GRID,
    tau_grid=None,
    window: float = 10.0,
):
    """Tune ``base_rate`` (and optionally ``tau``) to minimize training log loss.

    ``tau_grid=None`` keeps ``params0.tau`` fixed (a 1-D search, backwards
    compatible); pass a grid to also fit ``tau``. The search is an exhaustive but
    small grid — enough to pull the probabilities toward the real event rate
    without the machinery of a gradient optimizer.
    """
    taus = tau_grid if tau_grid is not None else (params0.tau,)
    best = params0
    best_cost = training_cost(train_matches, params0, window=window)
    for base_rate in base_rate_grid:
        for tau in taus:
            candidate = replace(params0, base_rate=base_rate, tau=tau)
            cost = training_cost(train_matches, candidate, window=window)
            if cost < best_cost:
                best_cost = cost
                best = candidate
    return best


def evaluate(matches, params, window: float = 10.0) -> dict:
    """Calibration metrics for ``params`` on ``matches`` (leakage-safe backtest)."""
    pairs = backtest(matches, params, window=window)["pairs"]
    n = len(pairs)
    return {
        "n": n,
        "brier": brier(pairs),
        "log_loss": log_loss(pairs),
        "mean_pred": sum(p for p, _ in pairs) / n,
        "base_freq": sum(o for _, o in pairs) / n,
        "reliability": reliability_curve(pairs, n_bands=10),
    }


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


def walk_forward_report(
    matches,
    params0,
    n_folds: int = 3,
    key=None,
    base_rate_grid=DEFAULT_BASE_RATE_GRID,
    tau_grid=DEFAULT_TAU_GRID,
    window: float = 10.0,
):
    """Fit on each expanding past window, evaluate on the next future block.

    Returns one dict per fold with the fitted parameters and the baseline-vs-fitted
    held-out metrics — the honest walk-forward test that the tuning generalizes
    rather than overfits (Section 21).
    """
    key = key or (lambda m: m.get("match_id"))
    folds = []
    for train, test in walk_forward_split(matches, n_folds=n_folds, key=key):
        fitted = fit_parameters(
            train, params0, base_rate_grid=base_rate_grid, tau_grid=tau_grid, window=window
        )
        folds.append(
            {
                "n_train": len(train),
                "n_test": len(test),
                "fitted_base_rate": fitted.base_rate,
                "fitted_tau": fitted.tau,
                "baseline": evaluate(test, params0, window=window),
                "fitted": evaluate(test, fitted, window=window),
            }
        )
    return folds
