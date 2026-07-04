"""Vision Engine (Inference): a continuous, self-correcting state of the match.

The colleague's Digital-Twin perception idea, built the FUT-K way — deterministic
and honest, without any computer vision. Every real located action is treated
as a **partial observation** of an entity's position at an instant. Between
observations the engine does not go blind: it maintains a continuous state
(position + velocity + confidence) and **predicts** where each player is, using
a constant-velocity motion model with drag. When the next real observation
arrives it does not "teach" the engine — it **corrects** it: the engine
measures its own prediction error (self-evaluation), snaps to the truth, and
resets confidence.

    observation → predict forward → next observation → error → correct → repeat

Confidence decays while an entity is unobserved and resets on re-observation,
so the twin knows exactly how much to trust each estimate. Everything here is a
pure function of the observation stream: same input, same output. No I/O, no
randomness, no CV models.

The philosophy shift the colleague named: from *"what is in this frame?"* to
*"what is the most likely state of the match right now, even where it can't be
directly observed?"*
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

# Pitch is 0-100 in each axis; ~1 unit ≈ 1 metre of the 105×68 m field. A very
# fast sprint is ~9 m/s, so cap extrapolated speed to keep predictions sane.
MAX_SPEED = 11.0          # units/second
DRAG = 0.82               # velocity retained per second while unobserved
CONF_HALF_LIFE = 20.0     # seconds for confidence to halve without observation
MAX_GAP = 120.0           # seconds after which an estimate is dropped as stale


@dataclass(frozen=True)
class EntityState:
    """One entity's estimated state at ``t`` seconds."""

    x: float
    y: float
    vx: float
    vy: float
    confidence: float
    last_obs_t: float     # when it was last really observed
    t: float              # the instant this state is valid for


def _confidence(base: float, dt: float, half_life: float) -> float:
    if dt <= 0:
        return base
    return round(base * 0.5 ** (dt / half_life), 4)


def predict(state: EntityState, t: float, *, drag: float = DRAG,
            half_life: float = CONF_HALF_LIFE,
            use_velocity: bool = False) -> EntityState:
    """Advance a state to time ``t``; confidence falls with time unobserved.

    ``use_velocity`` (default off) selects the motion model:

    * **off** — hold the last observed position. On sparse **event** data this
      is the validated-best estimate: a player's velocity *at a ball touch*
      barely predicts their next touch (see ``evaluate_prediction`` and
      validation §5.10), because touches involve stopping and turning.
    * **on** — constant-velocity with drag (``∫ drag^s ds``). Correct physics
      for **dense tracking** data with true running velocities; the machinery
      is ready for that source.

    Either way, confidence decays — the honest signal of how stale the estimate
    is. Deterministic.
    """
    dt = t - state.t
    if dt <= 0:
        return replace(state, t=t)
    if use_velocity:
        if drag <= 0 or drag >= 1:
            k = dt
        else:
            # ∫₀ᵈᵗ drag^s ds  = (drag^dt − 1) / ln(drag)
            k = (drag ** dt - 1.0) / math.log(drag)
        x = min(100.0, max(0.0, state.x + state.vx * k))
        y = min(100.0, max(0.0, state.y + state.vy * k))
        vx = state.vx * (drag ** dt)
        vy = state.vy * (drag ** dt)
    else:
        x, y, vx, vy = state.x, state.y, state.vx, state.vy
    conf = _confidence(state.confidence, t - state.last_obs_t, half_life)
    return EntityState(x, y, vx, vy, conf, state.last_obs_t, t)


def correct(state: EntityState | None, t: float, x: float, y: float) -> tuple:
    """Fold a real observation into the state; return ``(new_state, error)``.

    ``error`` is the distance (pitch units) between where the engine *predicted*
    the entity would be at ``t`` and where it actually was — the self-evaluation
    signal. Velocity is re-estimated from the real displacement since the last
    observation, capped at ``MAX_SPEED``. On correction, confidence resets to 1.
    A first observation has no prediction, so its error is ``None``.
    """
    if state is None:
        return EntityState(x, y, 0.0, 0.0, 1.0, t, t), None
    pred = predict(state, t, use_velocity=True)
    error = math.hypot(x - pred.x, y - pred.y)
    dt = t - state.last_obs_t
    if dt > 0:
        vx = (x - state.x) / dt
        vy = (y - state.y) / dt
        speed = math.hypot(vx, vy)
        if speed > MAX_SPEED:
            scale = MAX_SPEED / speed
            vx *= scale
            vy *= scale
    else:
        vx, vy = state.vx, state.vy
    return EntityState(x, y, vx, vy, 1.0, t, t), round(error, 3)


def _observations(stream_items, until_t=None):
    """Per-entity sorted (t, x, y) observations from the twin stream."""
    obs: dict = {}
    for it in stream_items:
        pid = it.get("player_id")
        if pid is None or it.get("x") is None or it.get("y") is None:
            continue
        if until_t is not None and it["t"] > until_t:
            continue
        obs.setdefault(pid, []).append((it["t"], it["x"], it["y"], it.get("player")))
    for pid in obs:
        obs[pid].sort(key=lambda o: o[0])
    return obs


def estimate_positions(stream_items, at_seconds: float, *,
                       drag: float = DRAG, half_life: float = CONF_HALF_LIFE,
                       max_gap: float = MAX_GAP,
                       use_velocity: bool = False) -> dict:
    """The continuous estimated state of every entity at ``at_seconds``.

    Feeds each entity's real observations up to ``at_seconds`` through the
    predict/correct loop, then predicts to ``at_seconds``. Returns
    ``{player_id: {name, x, y, vx, vy, confidence, age, observed}}`` where
    ``observed`` is True when an observation lands (near-)exactly at the
    instant, ``age`` is seconds since the last real observation, and stale
    entities (``age > max_gap``) are omitted — the engine honestly stops
    claiming to know where they are. ``use_velocity`` defaults off (the
    validated-best model on event data; see ``predict``).
    """
    obs = _observations(stream_items, until_t=at_seconds)
    out = {}
    for pid, seq in obs.items():
        state = None
        name = None
        for (t, x, y, nm) in seq:
            name = nm or name
            state, _ = correct(state, t, x, y)
        if state is None:
            continue
        est = predict(state, at_seconds, drag=drag, half_life=half_life,
                      use_velocity=use_velocity)
        age = at_seconds - state.last_obs_t
        if age > max_gap:
            continue
        out[pid] = {
            "name": name,
            "x": round(est.x, 2),
            "y": round(est.y, 2),
            "vx": round(est.vx, 3),
            "vy": round(est.vy, 3),
            "confidence": est.confidence,
            "age": round(age, 2),
            "observed": age < 0.05,
        }
    return out


def evaluate_prediction(stream_items, *, drag: float = DRAG,
                        min_obs: int = 4) -> dict:
    """Self-evaluation: how well the motion model predicts the next real touch.

    Walks each entity's real observations through the predict/correct loop and
    records, at every observation after the first, the distance between the
    predicted and the actually observed position. This is the engine grading
    itself on real data — no ground-truth beyond the data itself.

    Returns aggregate error stats (pitch units; ~1 unit ≈ 1 m) plus a naive
    baseline: the error of *not* predicting motion at all (assume the entity
    stayed where it was last seen). A motion model that beats "assume static"
    is genuinely modelling movement.
    """
    obs = _observations(stream_items)
    errors = []
    static_errors = []
    gaps = []
    for pid, seq in obs.items():
        if len(seq) < min_obs:
            continue
        state = None
        for (t, x, y, _nm) in seq:
            if state is not None:
                pred = predict(state, t, drag=drag, use_velocity=True)
                errors.append(math.hypot(x - pred.x, y - pred.y))
                static_errors.append(math.hypot(x - state.x, y - state.y))
                gaps.append(t - state.last_obs_t)
            state, _ = correct(state, t, x, y)
    if not errors:
        return {"n": 0}
    errors.sort()
    n = len(errors)
    mean = sum(errors) / n
    static_mean = sum(static_errors) / len(static_errors)
    return {
        "n": n,
        "entities": len(obs),
        "mean_error": round(mean, 3),
        "median_error": round(errors[n // 2], 3),
        "p90_error": round(errors[int(n * 0.9)], 3),
        "static_baseline_mean": round(static_mean, 3),
        "beats_static_by": round(static_mean - mean, 3),
        "mean_gap_seconds": round(sum(gaps) / len(gaps), 2),
    }
