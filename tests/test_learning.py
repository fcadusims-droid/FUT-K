"""C.21 — Continuous learning (Section 21)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fie.learning import (
    DEFAULT_BASE_RATE_GRID,
    DEFAULT_REGIME_SCALE_GRID,
    DEFAULT_TAU_GRID,
    evaluate,
    fit_parameters,
    fit_regime_scale,
    training_cost,
    walk_forward_report,
    walk_forward_split,
)
from fie.prediction import Params
from tests.conftest import SEEDS3
from tests.generators import league_simulator

TRUE_RATE = 0.015
WRONG_START = Params(base_rate=0.05)  # deliberately too high


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_fit_reduces_training_loss(seed):
    """T-21-01: fit_parameters reduces training log loss vs the untuned start."""
    train = league_simulator(60, TRUE_RATE, seed=seed)
    fitted = fit_parameters(train, WRONG_START)
    assert training_cost(train, fitted) < training_cost(train, WRONG_START)


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_fit_reduces_heldout_loss(seed):
    """T-21-02: the fitted parameters also reduce held-out log loss."""
    train = league_simulator(60, TRUE_RATE, seed=seed)
    heldout = league_simulator(60, TRUE_RATE, seed=seed + 1000)  # disjoint, same process
    fitted = fit_parameters(train, WRONG_START)
    assert training_cost(heldout, fitted) < training_cost(heldout, WRONG_START)


@pytest.mark.slow
def test_overfitting_canary():
    """T-21-03: fitting on a tiny, noisy training set can hurt held-out loss.

    Proves the walk-forward check has teeth: at least one seed must show held-out
    degradation relative to the untuned baseline.
    """
    baseline = Params(base_rate=TRUE_RATE)  # a decent, near-optimal baseline
    heldout = league_simulator(60, TRUE_RATE, seed=1234)
    baseline_loss = training_cost(heldout, baseline)

    degraded = False
    for seed in range(20):
        tiny_train = league_simulator(4, TRUE_RATE, seed=seed)
        fitted = fit_parameters(tiny_train, baseline)
        if training_cost(heldout, fitted) > baseline_loss:
            degraded = True
            break
    assert degraded, "overfitting canary never degraded — it needs a smaller/noisier regime"


@given(
    n=st.integers(min_value=4, max_value=40),
    n_folds=st.integers(min_value=1, max_value=5),
)
def test_walk_forward_no_overlap(n, n_folds):
    """T-21-04: a walk-forward split never overlaps train and test in time."""
    items = list(range(n))  # already a time-like ordering
    for train, test in walk_forward_split(items, n_folds=n_folds):
        assert max(train) < min(test)


def test_evaluate_shape_and_bounds():
    """evaluate() returns bounded calibration metrics on real-shaped matches."""
    matches = league_simulator(6, TRUE_RATE, seed=3)
    metrics = evaluate(matches, Params())
    assert set(metrics) >= {"n", "brier", "log_loss", "mean_pred", "base_freq", "reliability"}
    assert 0.0 <= metrics["brier"] <= 1.0
    assert 0.0 <= metrics["mean_pred"] <= 1.0
    assert 0.0 <= metrics["base_freq"] <= 1.0


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_fit_tau_grid_stays_in_grid(seed):
    """Fitting base_rate x tau returns grid values and never worsens training loss."""
    train = league_simulator(40, TRUE_RATE, seed=seed)
    fitted = fit_parameters(train, WRONG_START, tau_grid=DEFAULT_TAU_GRID)
    assert fitted.base_rate in DEFAULT_BASE_RATE_GRID
    assert fitted.tau in DEFAULT_TAU_GRID
    assert training_cost(train, fitted) <= training_cost(train, WRONG_START)


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_fit_regime_scale_calibrates_in_sample(seed):
    """Per-regime scale fitting never worsens in-sample log loss and stays in grid."""
    matches = league_simulator(60, TRUE_RATE, seed=seed)
    params = Params(base_rate=0.020)  # miscalibrated -> room for the scales to help
    fitted = fit_regime_scale(matches, params)

    assert fitted.regime_scale, "expected at least one regime calibrated"
    for value in fitted.regime_scale.values():
        assert value in DEFAULT_REGIME_SCALE_GRID or value == 1.0
    assert evaluate(matches, fitted)["log_loss"] <= evaluate(matches, params)["log_loss"] + 1e-9


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_walk_forward_closes_overprediction(seed):
    """A too-high base rate over-predicts; walk-forward fitting closes the gap.

    Mirrors the real-data finding: an over-confident predictor is pulled toward
    the true event frequency out of sample, improving held-out log loss.
    """
    low_rate = 0.010
    over_confident = Params(base_rate=0.020)  # predicts too many goals
    matches = league_simulator(48, low_rate, seed=seed)

    folds = walk_forward_report(matches, over_confident, n_folds=3, tau_grid=DEFAULT_TAU_GRID)
    assert folds, "expected at least one walk-forward fold"

    base_gap = sum(abs(f["baseline"]["mean_pred"] - f["baseline"]["base_freq"]) for f in folds)
    fit_gap = sum(abs(f["fitted"]["mean_pred"] - f["fitted"]["base_freq"]) for f in folds)
    base_loss = sum(f["baseline"]["log_loss"] for f in folds)
    fit_loss = sum(f["fitted"]["log_loss"] for f in folds)

    assert fit_gap < base_gap        # over-prediction shrinks out of sample
    assert fit_loss < base_loss      # and held-out log loss improves
