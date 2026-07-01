"""Tactical & Collective Intelligence (Section 14).

Section 14 is the most qualitative module in the spec. Per the plan's guidance we
pin the decision rules down explicitly here (short, documented heuristics) and
then test against *these* rules — never a vague test against a vague rule.

Pitch convention: ``x`` in ``[0, 100]``. A team's attacking direction is given by
``attack_right``; ``attack_right=True`` means the team attacks toward ``x = 100``.
The defensive third is the first third of the pitch in the team's own direction,
the attacking third the last.
"""

from __future__ import annotations

from collections import defaultdict

# A "counter-attack" is a defensive-third recovery followed by an attacking-third
# action by the same team within this many minutes (~10 seconds).
COUNTER_MAX_GAP = 10.0 / 60.0


def _oriented_x(x: float, attack_right: bool) -> float:
    """x flipped so the team always attacks toward 100."""
    return x if attack_right else 100.0 - x


def thirds_distribution(events, team: str, attack_right: bool = True) -> dict:
    """Share of ``team``'s positioned events in each pitch third."""
    own = mid = att = 0
    for e in events:
        if e.team != team or e.x is None:
            continue
        x = _oriented_x(e.x, attack_right)
        if x < 100 / 3:
            own += 1
        elif x > 200 / 3:
            att += 1
        else:
            mid += 1
    total = own + mid + att
    if total == 0:
        return {"own": 0.0, "mid": 0.0, "att": 0.0}
    return {"own": own / total, "mid": mid / total, "att": att / total}


def _has_counter(events, team: str, attack_right: bool) -> bool:
    team_events = sorted(
        (e for e in events if e.team == team and e.x is not None),
        key=lambda e: e.minute,
    )
    for a, b in zip(team_events, team_events[1:]):
        xa = _oriented_x(a.x, attack_right)
        xb = _oriented_x(b.x, attack_right)
        if xa < 100 / 3 and xb > 200 / 3 and (b.minute - a.minute) <= COUNTER_MAX_GAP:
            return True
    return False


def detect_tactic(events, team: str, attack_right: bool = True) -> str:
    """Classify what ``team`` is trying to do, from positions + timing.

    Decision rule (checked in order):
      1. ``counter_attack`` — a fast defensive-third -> attacking-third transition.
      2. ``low_block``      — most positioned events in the own defensive third.
      3. ``high_press``     — most positioned events in the attacking third.
      4. ``mid_block``      — everything else.
    """
    if _has_counter(events, team, attack_right):
        return "counter_attack"
    dist = thirds_distribution(events, team, attack_right)
    if dist["own"] > 0.5:
        return "low_block"
    if dist["att"] > 0.5:
        return "high_press"
    return "mid_block"


# --------------------------------------------------------------------------- #
# Collective Intelligence — properties read off the passing network
# --------------------------------------------------------------------------- #
def _node_strengths(network) -> dict:
    strength = defaultdict(float)
    for (a, b), d in network.items():
        strength[a] += d["weight"]
        strength[b] += d["weight"]
    return strength


def team_robustness(network) -> float:
    """1 - Herfindahl concentration of node strengths, in ``[0, 1]``.

    A star-shaped network (one hub) concentrates strength -> low robustness. An
    evenly distributed network spreads it -> high robustness.
    """
    strength = _node_strengths(network)
    total = sum(strength.values())
    if total == 0:
        return 0.0
    shares = [s / total for s in strength.values()]
    return 1.0 - sum(s * s for s in shares)


def dependence_on_key_players(network) -> float:
    """The single busiest node's share of all strength, in ``[0, 1]``."""
    strength = _node_strengths(network)
    total = sum(strength.values())
    if total == 0:
        return 0.0
    return max(strength.values()) / total


def cohesion(network) -> float:
    """How evenly the team is connected, in ``[0, 1]`` (== robustness)."""
    return team_robustness(network)


def fluidity(network) -> float:
    """Fraction of realized directed connections among all possible, ``[0, 1]``."""
    nodes = {n for edge in network for n in edge}
    k = len(nodes)
    if k < 2:
        return 0.0
    return min(1.0, len(network) / (k * (k - 1)))
