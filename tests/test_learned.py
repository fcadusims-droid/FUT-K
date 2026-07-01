"""Section 21 Stage 3 — learned logistic model (offline)."""

from __future__ import annotations

import numpy as np

from fie.calibration import log_loss
from fie.events import Event
from fie.learned import (
    LogisticModel,
    evaluate_model,
    snapshot_dataset,
    train_model,
)
from fie.prediction import Params
from tests.generators import league_simulator


def test_logistic_learns_a_pattern():
    """Gradient descent recovers a linear signal: beats a constant predictor."""
    rng = np.random.default_rng(0)
    n = 1500
    x0 = rng.normal(size=n)
    p = 1.0 / (1.0 + np.exp(-(0.5 + 2.0 * x0)))
    y = (rng.random(n) < p).astype(int)
    X = [[float(v)] for v in x0]

    model = LogisticModel().fit(X, list(y))
    preds = [model.predict_proba_features([float(v)]) for v in x0]
    ll_model = log_loss(list(zip(preds, y.tolist())))

    base = float(y.mean())
    ll_const = log_loss([(base, int(v)) for v in y])
    assert ll_model < ll_const


def test_features_are_leakage_safe():
    """Features at minute t are unchanged by events appended after t (T-20-04)."""
    events = [Event("m", 10, "HOME", "shot"), Event("m", 20, "AWAY", "shot_on_target")]
    match = {"match_id": "m", "events": events, "duration": 90, "eval_minutes": [30]}
    X1, _ = snapshot_dataset([match], Params())

    future = events + [Event("m", 40, "HOME", "goal"), Event("m", 50, "AWAY", "shot")]
    match2 = {"match_id": "m", "events": future, "duration": 90, "eval_minutes": [30]}
    X2, _ = snapshot_dataset([match2], Params())

    assert X1 == X2  # identical features despite different futures


def test_evaluate_model_bounded():
    """train_model / evaluate_model run and return bounded metrics."""
    matches = league_simulator(12, 0.015, seed=3)
    model = train_model(matches, Params())
    metrics = evaluate_model(model, matches, Params())
    assert 0.0 <= metrics["brier"] <= 1.0
    assert metrics["log_loss"] >= 0.0
    assert metrics["n"] > 0
