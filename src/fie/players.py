"""Individual Intelligence — behavioral player modeling (Section 12).

No real psychology is assumed — only observed behavior, in probabilities. The
layers build on each other: profile -> archetype -> influence -> network ->
avatar -> player-aware lambda.
"""

from __future__ import annotations

from collections import defaultdict

from .prediction import rates


# --------------------------------------------------------------------------- #
# Layer 2 — decisional profile
# --------------------------------------------------------------------------- #
def decision_profile(player_events, zone) -> dict:
    """Distribution of the next action given a reception in ``zone``.

    ``player_events`` are records with ``.type``, ``.zone`` and ``.next_action``.
    Returns a probability distribution over {shot, pass, dribble, drop} that sums
    to 1.0, or all-zero when there is no data for the zone.
    """
    counts = {"shot": 0, "pass": 0, "dribble": 0, "drop": 0}
    for r in player_events:
        if getattr(r, "type", None) == "reception" and getattr(r, "zone", None) == zone:
            act = getattr(r, "next_action", None)
            if act in counts:
                counts[act] += 1
    total = sum(counts.values())
    if total == 0:
        return {k: 0.0 for k in counts}
    return {k: v / total for k, v in counts.items()}


# --------------------------------------------------------------------------- #
# Layer 3 — statistical "psychological" profile (archetypes)
# --------------------------------------------------------------------------- #
def archetype(p: dict) -> str:
    """Classify an archetype from observed behavior — pure statistics."""
    if p.get("shot_frequency", 0) > 0.4 and p.get("time_to_shot", 99) < 2:
        return "finisher"
    if p.get("progressive_pass", 0) > 0.15 and p.get("assist_frequency", 0) > 0.3:
        return "creator"
    if p.get("turnover_rate", 0) > 0.2 and p.get("hard_dribbles", 0) > 0.3:
        return "impulsive"
    if p.get("risk", 1) < 0.1 and p.get("lateral_passes", 0) > 0.6:
        return "conservative"
    return "balanced"


# --------------------------------------------------------------------------- #
# Layer 4 — influence model (on/off)
# --------------------------------------------------------------------------- #
def goal_influence(lambda_on: float, lambda_off: float) -> float:
    """Descriptive on/off influence: the team's rate delta with the player on."""
    return lambda_on - lambda_off


# --------------------------------------------------------------------------- #
# Layer 5 — interaction network
# --------------------------------------------------------------------------- #
def passing_network(pass_events) -> dict:
    """Directed graph of who passes to whom (successful passes only)."""
    graph = defaultdict(lambda: {"weight": 0, "chances": 0})
    for p in pass_events:
        if getattr(p, "success", False):
            graph[(p.from_, p.to)]["weight"] += 1
            if getattr(p, "created_chance", False):
                graph[(p.from_, p.to)]["chances"] += 1
    return dict(graph)


def critical_links(graph, top: int = 3):
    """The ``top`` highest-volume nodes in the passing network."""
    strength = defaultdict(int)
    for (a, b), d in graph.items():
        strength[a] += d["weight"]
        strength[b] += d["weight"]
    return sorted(strength, key=strength.get, reverse=True)[:top]


# --------------------------------------------------------------------------- #
# Layer 6 — statistical avatar
# --------------------------------------------------------------------------- #
# Reference ranges used to normalize each avatar dimension into [0, 1].
AVATAR_RANGES = {
    "avg_hold_seconds": (0.0, 5.0),
    "pass_accuracy": (0.0, 1.0),
    "progressive_pass": (0.0, 1.0),
    "shot_frequency": (0.0, 1.0),
    "assist_frequency": (0.0, 1.0),
    "turnover_rate": (0.0, 1.0),
}


def avatar(profile: dict, ranges: dict = AVATAR_RANGES) -> dict:
    """Normalize a raw profile into a comparable ``[0, 1]`` vector."""
    out = {}
    for key, (lo, hi) in ranges.items():
        raw = profile.get(key, lo)
        span = hi - lo
        val = 0.0 if span == 0 else (raw - lo) / span
        out[key] = min(1.0, max(0.0, val))
    return out


# --------------------------------------------------------------------------- #
# Integration — player-aware lambda
# --------------------------------------------------------------------------- #
def collective_rate(state, team: str, events, params, regime=None) -> float:
    """The team's collective goal rate from Sections 7-8 (no player data)."""
    lam_home, lam_away = rates(state, events, params, regime=regime)
    return lam_home if team == "HOME" else lam_away


def player_aware_lambda(
    state,
    team: str,
    events,
    params,
    profiles=None,
    network=None,
    mult_lineup: float = 1.0,
    network_bonus: float = 1.0,
    regime=None,
) -> float:
    """Collective rate scaled by lineup form (Layer 4) and network bonus (Layer 5).

    Reduces exactly to ``collective_rate`` when both factors are 1 (T-12-09).
    """
    base = collective_rate(state, team, events, params, regime=regime)
    return base * mult_lineup * network_bonus
