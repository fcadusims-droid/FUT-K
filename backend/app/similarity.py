"""Semantic match search (product level 7): "matches that felt like this one".

Each match gets an **engine-native embedding** — a fixed-length vector of its
game-state dynamics (momentum trajectory, goal-timing histogram, event volumes,
lead swings). Similarity is cosine distance between vectors. No external model:
the "semantics" here are the semantics of how the match *flowed*, computed from
the same validated engine features the panel uses — deterministic, reproducible
and explainable.
"""

from __future__ import annotations

import math

from fie.indices import momentum_index
from fie.prediction import Params

CHECKPOINTS = (15.0, 30.0, 45.0, 60.0, 75.0, 90.0)
GOAL_BINS = ((0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 200))

# Fixed normalization scales so every dimension lands in ~[0, 1].
SCALES = {"goals": 3.0, "shots": 15.0, "corners": 8.0, "cards": 4.0}


def _lead_swings(goals) -> tuple:
    h = a = max_h = max_a = changes = 0
    leader = 0
    for _, team in goals:
        h += team == "HOME"
        a += team == "AWAY"
        max_h = max(max_h, h - a)
        max_a = max(max_a, a - h)
        new_leader = (h > a) - (h < a)
        if new_leader != leader and new_leader != 0:
            changes += 1
        leader = new_leader
    return max_h, max_a, changes


def match_vector(events, params: Params | None = None) -> list:
    """The match's dynamics embedding (length 22), each dim in ~[0, 1]."""
    params = params or Params()
    goals = [(e.minute, e.team) for e in events if e.type == "goal"]

    # Momentum trajectory at fixed checkpoints (the shape of control).
    momentum = [
        momentum_index([e for e in events if e.minute <= t], t, params.tau)
        for t in CHECKPOINTS
    ]

    # When the goals came (normalized histogram over both teams).
    hist = [
        sum(1 for m, _ in goals if lo <= m < hi) / SCALES["goals"]
        for lo, hi in GOAL_BINS
    ]

    def count(*types):
        return sum(1 for e in events if e.type in types)

    max_h, max_a, changes = _lead_swings(goals)
    volumes = [
        min(1.0, count("shot", "shot_on_target") / SCALES["shots"]),
        min(1.0, count("corner") / SCALES["corners"]),
        min(1.0, count("yellow_card", "red_card") / SCALES["cards"]),
        min(1.0, len(goals) / (2 * SCALES["goals"])),
    ]
    drama = [
        min(1.0, max_h / SCALES["goals"]),
        min(1.0, max_a / SCALES["goals"]),
        min(1.0, changes / 3.0),
        1.0 if any(m >= 85 for m, _ in goals) else 0.0,  # late drama
        min(1.0, count("red_card") / 2.0),
        abs(momentum[-1] - 0.5) * 2,  # how one-sided it ended
    ]
    return momentum + hist + volumes + drama


def cosine(u, v) -> float:
    dot = sum(a * b for a, b in zip(u, v))
    nu = math.sqrt(sum(a * a for a in u))
    nv = math.sqrt(sum(b * b for b in v))
    return dot / (nu * nv) if nu and nv else 0.0


def similar_matches(target_vector, candidates: dict, limit: int = 5) -> list:
    """Rank candidate matches ({id: vector}) by cosine similarity."""
    ranked = sorted(
        ((mid, cosine(target_vector, vec)) for mid, vec in candidates.items()),
        key=lambda kv: -kv[1],
    )
    return ranked[:limit]
