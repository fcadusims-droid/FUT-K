"""C.20 — Validation and calibration (Section 20). Validates the validator."""

from __future__ import annotations

import pytest

from fie.calibration import (
    backtest,
    brier,
    log_loss,
    max_reliability_deviation,
    reliability_curve,
)
from fie.events import Event
from fie.prediction import Params, prob_event_within
from tests.conftest import MULTI_SEEDS, SEEDS3
from tests.generators import goal_window_snapshots


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_brier_of_calibrated_predictor(seed):
    """T-20-01: Brier of a perfectly calibrated predictor reproduces ~0.190."""
    # Constant total rate 0.03/min over a 10-min window -> p = 1 - e^-0.3 ~ 0.259,
    # whose irreducible Brier is p(1-p) ~ 0.192.
    _, p_true, outcomes = goal_window_snapshots(
        n=200_000, window=10, seed=seed, lam_low=0.03, lam_high=0.03
    )
    pairs = list(zip(p_true, outcomes))
    assert abs(brier(pairs) - 0.190) < 0.01


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_biased_predictor_is_worse(seed):
    """T-20-02: a biased predictor (λ×1.4) scores a worse Brier and a bent curve."""
    lam, p_true, outcomes = goal_window_snapshots(
        n=200_000, window=10, seed=seed, lam_low=0.03, lam_high=0.03
    )
    calibrated = list(zip(p_true, outcomes))
    p_biased = 1.0 - __import__("numpy").exp(-1.4 * lam * 10)
    biased = list(zip(p_biased, outcomes))

    assert brier(biased) > brier(calibrated)
    # The biased curve visibly departs from the diagonal (predicted > observed);
    # the absolute band (~0.34 predicted vs ~0.26 observed here) is fixed by the
    # base λ chosen to make T-20-01 land on 0.190 — the mechanism is the point.
    assert max_reliability_deviation(biased) > 0.05
    assert max_reliability_deviation(calibrated) < 0.02


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS3)
def test_reliability_curve_on_diagonal(seed):
    """T-20-03: reliability_curve on a calibrated predictor lies on the diagonal."""
    _, p_true, outcomes = goal_window_snapshots(
        n=400_000, window=10, seed=seed, lam_low=0.02, lam_high=0.06
    )
    pairs = list(zip(p_true, outcomes))
    curve = reliability_curve(pairs, n_bands=10)
    assert len(curve) >= 3  # several bands populated
    assert max_reliability_deviation(pairs, n_bands=10) <= 0.01


def test_backtest_has_no_leakage():
    """T-20-04: prediction at minute t is unchanged by events appended after t."""
    events = [
        Event("m", 10, "HOME", "shot"),
        Event("m", 20, "AWAY", "shot_on_target"),
        Event("m", 25, "HOME", "corner"),
    ]
    match = {"match_id": "m", "events": list(events), "duration": 90,
             "eval_minutes": [30]}
    first = backtest([match], Params())["predictions"][0]["prob"]

    # Append future events (including a goal) after minute 30 and re-run.
    future = events + [
        Event("m", 35, "AWAY", "goal"),
        Event("m", 40, "HOME", "shot_on_target"),
        Event("m", 55, "AWAY", "shot"),
    ]
    match2 = {"match_id": "m", "events": future, "duration": 90, "eval_minutes": [30]}
    second = backtest([match2], Params())["predictions"][0]["prob"]

    assert first == second  # byte-for-byte identical


@pytest.mark.slow
@pytest.mark.parametrize("seed", MULTI_SEEDS)
def test_no_signal_world_lands_on_noise_floor(seed):
    """T-20-05: a no-signal world produces Brier at the theoretical noise floor."""
    _, p_true, outcomes = goal_window_snapshots(
        n=100_000, window=10, seed=seed, lam_low=0.03, lam_high=0.03
    )
    pairs = list(zip(p_true, outcomes))
    p = float(p_true[0])
    noise_floor = p * (1 - p)
    assert abs(brier(pairs) - noise_floor) < 0.01


def test_brier_empty_raises():
    """T-20-06: brier() / log_loss() raise on empty input, not divide-by-zero."""
    with pytest.raises(ValueError):
        brier([])
    with pytest.raises(ValueError):
        log_loss([])


def test_backtest_smoke():
    """Sanity: backtest runs and produces the expected record shape."""
    match = {
        "match_id": "s",
        "events": [Event("s", 30, "HOME", "goal")],
        "duration": 90,
        "eval_minutes": [10, 20],
    }
    result = backtest([match], Params(), window=10)
    assert set(result["predictions"][0]) == {"match_id", "minute", "target", "prob"}
    # The 20' snapshot predicts a goal within (20, 30]; the outcome is 1.
    assert result["pairs"][1][1] == 1
    for prob, _ in result["pairs"]:
        assert 0.0 <= prob <= 1.0
