"""Continuous learning — Stage 3: a learned model (Section 21).

Replaces the heuristic intensity formula with a small logistic-regression model
that takes leakage-safe game-state features and predicts the goal-in-window
probability directly. Standard-library only (plain gradient descent), so it stays
within the ``src/fie`` no-dependencies rule. Whether it actually beats the
heuristic is decided out of sample by walk-forward validation — never assumed.
"""

from __future__ import annotations

import math

from .calibration import brier, log_loss
from .events import state_from_events
from .indices import momentum_index, offensive_pressure

# Recent shots in this trailing window feed the "shot rate" feature.
SHOT_WINDOW = 10.0


def _sigmoid(z):
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def snapshot_features(state, events_until, params):
    """Leakage-safe feature vector for one minute (uses only events <= minute)."""
    ph = offensive_pressure(events_until, "HOME", state.minute, params.tau)
    pa = offensive_pressure(events_until, "AWAY", state.minute, params.tau)
    mom = momentum_index(events_until, state.minute, params.tau)
    recent_shots = sum(
        1 for e in events_until
        if e.type in ("shot", "shot_on_target") and state.minute - e.minute <= SHOT_WINDOW
    )
    return [
        ph + pa,                                  # total offensive pressure
        max(mom, 1.0 - mom),                      # dominance of the stronger side
        state.minute / 90.0,                      # time
        1.0 if state.minute >= 75 else 0.0,       # end-game
        float(abs(state.home_goals - state.away_goals)),  # score closeness
        float(recent_shots),                      # recent shot volume
    ]


class LogisticModel:
    """A tiny standardized logistic regression trained by gradient descent."""

    def __init__(self):
        self.w = None      # weights (bias first)
        self.mean = None
        self.std = None

    def fit(self, X, y, lr=0.3, epochs=800, l2=1e-4):
        n = len(X)
        d = len(X[0])
        self.mean = [sum(row[j] for row in X) / n for j in range(d)]
        self.std = [
            (sum((row[j] - self.mean[j]) ** 2 for row in X) / n) ** 0.5 or 1.0
            for j in range(d)
        ]
        Xs = [[(row[j] - self.mean[j]) / self.std[j] for j in range(d)] for row in X]
        self.w = [0.0] * (d + 1)
        for _ in range(epochs):
            grad = [0.0] * (d + 1)
            for xi, yi in zip(Xs, y):
                p = _sigmoid(self.w[0] + sum(self.w[j + 1] * xi[j] for j in range(d)))
                err = p - yi
                grad[0] += err
                for j in range(d):
                    grad[j + 1] += err * xi[j]
            self.w[0] -= lr * grad[0] / n
            for j in range(d):
                self.w[j + 1] -= lr * (grad[j + 1] / n + l2 * self.w[j + 1])
        return self

    def predict_proba_features(self, x):
        xs = [(x[j] - self.mean[j]) / self.std[j] for j in range(len(x))]
        return _sigmoid(self.w[0] + sum(self.w[j + 1] * xs[j] for j in range(len(xs))))


def snapshot_dataset(matches, params, window=10.0, eval_step=5):
    """Build ``(X, y)`` from leakage-safe per-minute snapshots across matches."""
    X, y = [], []
    for match in matches:
        match_id = match.get("match_id", "")
        all_events = sorted(match["events"], key=lambda e: e.minute)
        duration = int(match.get("duration", 90))
        eval_minutes = match.get("eval_minutes")
        if eval_minutes is None:
            last = max(eval_step, duration - int(window))
            eval_minutes = range(eval_step, last + 1, eval_step)
        for t in eval_minutes:
            events_until = [e for e in all_events if e.minute <= t]
            state = state_from_events(match_id, all_events, t)
            X.append(snapshot_features(state, events_until, params))
            happened = 1 if any(
                e.type == "goal" and t < e.minute <= t + window for e in all_events
            ) else 0
            y.append(happened)
    return X, y


def train_model(matches, params, window=10.0):
    """Train the learned model on a set of matches."""
    X, y = snapshot_dataset(matches, params, window)
    return LogisticModel().fit(X, y)


def evaluate_model(model, matches, params, window=10.0):
    """Held-out calibration metrics for a learned model."""
    X, y = snapshot_dataset(matches, params, window)
    pairs = [(model.predict_proba_features(x), yi) for x, yi in zip(X, y)]
    return {"n": len(pairs), "brier": brier(pairs), "log_loss": log_loss(pairs)}
