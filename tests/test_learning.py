"""C.21 — Continuous learning (Section 21)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fie.learning import fit_parameters, training_cost, walk_forward_split
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
