"""Scout AI foundations (Inference): behavioral similarity + a transparent
scouting index over player DNA profiles.

Three honest primitives, standard-library only, deterministic:

* **Similarity** — cosine distance between normalized behavioral profile
  vectors. It answers *"whose observed playing profile does this player's
  resemble?"* — proximity of behavior, **not** current quality and **not** a
  potential prediction.
* **Cohort percentiles** — where a player's rates sit inside a real cohort
  (e.g. same position, same competition). Percentiles are computed against the
  actually-ingested population, never against invented reference values.
* **Scout index** — a documented, descriptive 0–100 composite of those
  percentiles, weighted by profile confidence (evidence volume) and, when a
  real birth date is known, an age factor (younger = more development runway).

The index is a *transparent heuristic*, not a trained model: every component
is exposed in the output, and the honest upgrade path — learning real
development trajectories — needs longitudinal youth data that free sources do
not yet provide (see docs/SCOUT.md). Nothing here fabricates a data point.
"""

from __future__ import annotations

import math
from datetime import date

# Fixed normalization ranges for the behavioral vector (documented; the same
# real-football spans used by the avatar in fie.profiling). Each feature maps
# to [0, 1]; rates outside the span clamp.
VECTOR_RANGES: tuple = (
    ("pass_accuracy", 0.5, 1.0),
    ("progressive_pass_share", 0.0, 0.4),
    ("key_pass_rate", 0.0, 0.10),
    ("shot_share", 0.0, 0.15),
    ("turnover_rate", 0.0, 0.10),
    ("goal_rate", 0.0, 0.05),      # goals per on-ball action
    ("assist_rate", 0.0, 0.03),    # assists per on-ball action
)

# Age factor bounds: a documented, descriptive prior about development runway.
AGE_YOUNG, AGE_OLD = 19.0, 32.0
FACTOR_YOUNG, FACTOR_OLD = 1.15, 0.85


def _rate(profile: dict, num: str, den: str = "actions") -> float:
    d = profile.get(den) or 0
    return (profile.get(num) or 0) / d if d else 0.0


def profile_vector(profile: dict) -> list:
    """Normalized [0,1] behavioral vector from a profile's observed rates."""
    src = dict(profile)
    src["goal_rate"] = _rate(profile, "goals")
    src["assist_rate"] = _rate(profile, "assists")
    # Accept both the engine key and the stored-column name for progression.
    if "progressive_pass_share" not in src and "progressive_pass" in src:
        src["progressive_pass_share"] = src["progressive_pass"]
    out = []
    for key, lo, hi in VECTOR_RANGES:
        raw = src.get(key)
        raw = lo if raw is None else raw
        span = hi - lo
        v = 0.0 if span == 0 else (raw - lo) / span
        out.append(min(1.0, max(0.0, v)))
    return out


def cosine(u: list, v: list) -> float:
    dot = sum(a * b for a, b in zip(u, v))
    nu = math.sqrt(sum(a * a for a in u))
    nv = math.sqrt(sum(b * b for b in v))
    return dot / (nu * nv) if nu and nv else 0.0


def similar_players(target: dict, candidates: dict, limit: int = 5) -> list:
    """Rank ``candidates`` ({player_id: profile}) by behavioral similarity.

    Returns ``[(player_id, similarity 0..1), ...]`` best first. Similarity of
    *observed behavior* — the payload's caller must say so.
    """
    tv = profile_vector(target)
    ranked = sorted(
        ((pid, cosine(tv, profile_vector(p))) for pid, p in candidates.items()),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return ranked[:limit]


def percentile(value: float, population: list) -> float:
    """Fraction of ``population`` strictly below ``value`` (0..1), plus half of
    ties — the standard mid-rank percentile. Empty population -> 0.5 (unknown).
    """
    if not population:
        return 0.5
    below = sum(1 for v in population if v < value)
    ties = sum(1 for v in population if v == value)
    return (below + 0.5 * ties) / len(population)


def age_on(birth_date: str, on: str) -> float | None:
    """Age in years on a given ISO date; None when either date is missing/bad."""
    try:
        b = date.fromisoformat(birth_date[:10])
        o = date.fromisoformat(on[:10])
    except (TypeError, ValueError):
        return None
    return round((o - b).days / 365.2425, 2)


def age_factor(age: float | None) -> float:
    """Development-runway factor: 1.15 at <=19, 1.0 mid-career, 0.85 at >=32.
    Unknown age -> exactly 1.0 (neutral — never a guessed bonus)."""
    if age is None:
        return 1.0
    if age <= AGE_YOUNG:
        return FACTOR_YOUNG
    if age >= AGE_OLD:
        return FACTOR_OLD
    span = AGE_OLD - AGE_YOUNG
    return round(FACTOR_YOUNG + (FACTOR_OLD - FACTOR_YOUNG) * ((age - AGE_YOUNG) / span), 4)


def scout_index(percentiles: dict, confidence: float | None, age: float | None) -> dict:
    """The transparent scouting composite, 0..100.

    ``percentiles``: component name -> cohort percentile (0..1); typically
    attack / creation / progression / security. The score is::

        100 * mean(percentiles) * (0.5 + 0.5*confidence) * age_factor(age)

    capped at 100. Confidence (evidence volume, 0..1) can only *shrink* a thin
    profile toward half-weight — a player seen for 40 actions never outranks an
    equal player seen for 900. Every term is returned; the note states what the
    number is (a descriptive index) and is explicit when age is unknown.
    """
    comps = {k: round(v, 3) for k, v in percentiles.items()}
    perf = sum(comps.values()) / len(comps) if comps else 0.0
    conf = 0.0 if confidence is None else max(0.0, min(1.0, confidence))
    af = age_factor(age)
    score = min(100.0, round(100.0 * perf * (0.5 + 0.5 * conf) * af, 1))
    return {
        "score": score,
        "components": comps,
        "performance": round(perf, 3),
        "confidence_weight": round(0.5 + 0.5 * conf, 3),
        "age": age,
        "age_factor": af,
        "note": (
            "Descriptive scouting index — cohort percentiles of observed rates, "
            "weighted by evidence volume"
            + (" and age (development runway)." if age is not None
               else "; age unknown, so no age factor was applied.")
            + " Not a trained potential prediction."
        ),
    }
