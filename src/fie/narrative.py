"""Narrative Intelligence — perception vs reality (Section 15).

Treats what people say as a hypothesis to verify, not as truth, purely to
understand the game better. Data = evidence; opinion = hypothesis; system =
verifier.
"""

from __future__ import annotations

import math

# Robust opinion signals, English- and Portuguese-flavored (Section 15.1). Kept
# small on purpose — irony and slang break bigger models.
NEG = {
    "bad", "poor", "awful", "weak", "lost", "anonymous", "finished",
    "ruim", "pessimo", "péssimo", "fraco", "horrivel", "horrível", "apagado",
}
POS = {
    "good", "great", "brilliant", "strong", "decisive",
    "bom", "otimo", "ótimo", "brilhante", "forte", "decisivo",
}


def opinion_to_hypothesis(text: str, target, aspect: str = "performance") -> dict:
    """Turn a free-text opinion into a testable, directional hypothesis."""
    t = (text or "").lower()
    if any(w in t for w in NEG):
        direction = "worse"
    elif any(w in t for w in POS):
        direction = "better"
    else:
        direction = "same"
    return {"target": target, "aspect": aspect, "direction": direction}


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def classify(direction: str, z: float) -> str:
    """Classify a hypothesis given the standardized deviation ``z`` of the data."""
    s = {"better": 1, "worse": -1, "same": 0}[direction]
    sz, az = _sign(z), abs(z)
    if direction == "same":
        if az <= 0.5:
            return "Confirmed"
        if az > 1.5:
            return "Strongly contradicted"
        return "Not confirmed"
    if s == sz and az > 1.5:
        return "Confirmed"
    if s == sz and az > 0.5:
        return "Partially confirmed"
    if s != sz and az > 1.5:
        return "Strongly contradicted"
    return "Not confirmed"


def verify(hypothesis: dict, real: float, ref_mean: float, ref_std: float) -> str:
    """Verify a hypothesis against the data. Never crashes, never false-confirms.

    Pathological inputs (non-finite ``real``/refs, or a zero reference spread)
    yield an explicit ``"Not confirmed"`` rather than a misleading label (T-15-10).
    """
    if not (math.isfinite(real) and math.isfinite(ref_mean) and math.isfinite(ref_std)):
        return "Not confirmed"
    if ref_std <= 0:
        return "Not confirmed"
    z = (real - ref_mean) / ref_std
    return classify(hypothesis["direction"], z)


def divergence(perception: float, reality: float) -> float:
    """Absolute distance between perception and reality — symmetric, non-negative."""
    return abs(reality - perception)


def divergence_index(target, sources, data, *, weighted_sentiment=None,
                     objective_score=None) -> float:
    """Distance between weighted public perception and the objective score.

    The perception/reality scorers are injectable; both default to returning 0
    so the module imports and runs without the full social scaffolding.
    """
    weighted_sentiment = weighted_sentiment or (lambda s, t: 0.0)
    objective_score = objective_score or (lambda t, d: 0.0)
    perception = weighted_sentiment(sources, target)
    reality = objective_score(target, data)
    return divergence(perception, reality)


def update_credibility(source: dict, label: str) -> float:
    """Update a source's weight from historical accuracy (not fame)."""
    hit = label in {"Confirmed", "Partially confirmed"}
    source["hits"] = source.get("hits", 0) + (1 if hit else 0)
    source["total"] = source.get("total", 0) + 1
    source["weight"] = source["hits"] / source["total"]
    return source["weight"]


def collective_state(emotion: float, reality: float, threshold: float = 40.0) -> dict:
    """Collective emotional state and whether it has detached from the data.

    ``overreaction`` is a pure function of ``abs(emotion - reality) > threshold``
    (T-15-08) — no hidden dependence on the absolute emotion/reality levels.
    """
    div = abs(emotion - reality)
    return {
        "emotion": emotion,
        "reality": reality,
        "divergence": div,
        "overreaction": div > threshold,
    }


def update_narrative_memory(memory: dict, pattern: str, confirmed: bool) -> float:
    """Update the reliability of a recurring narrative pattern against history."""
    m = memory.setdefault(pattern, {"confirmed": 0, "total": 0, "rate": 0.0})
    m["total"] += 1
    m["confirmed"] += 1 if confirmed else 0
    m["rate"] = m["confirmed"] / m["total"]
    return m["rate"]
