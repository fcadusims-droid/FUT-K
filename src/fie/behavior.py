"""Behavioral Intelligence — player behavior from event sequences (Knowledge).

The vision's behavioral layer (docs/design/DATASET_FUSION.md category 8): indices
inferred from *how a player behaves on the pitch* — Decision Stability, Pressure
Resistance, Aggression Control, Resilience, a Confidence Curve. Built only from
observed event sequences, in the same honest spirit as ``fie.profiling``: each
index is a documented, bounded function of real signals, carries the profile's
evidence-based confidence, and — crucially — **abstains** (returns ``None`` with a
stated reason) when the data cannot support it. Leadership, Recovery Behavior and
Tactical Discipline need signals the normalized event stream does not carry
(captaincy, tackles/interceptions/pressures, positional role adherence), so they
are honestly abstained rather than fabricated.

Descriptive, not predictive: these are readings of observed behavior, not claims
about a player's character. Pure and deterministic; standard library only.
"""

from __future__ import annotations

from typing import Optional

# Reference rates that map a raw signal into [0, 1]. Documented, tunable, and
# chosen from the same real-football ranges profiling.py already uses.
REF_TURNOVER = 0.10        # turnovers/action at which stability bottoms out
REF_DISCIPLINE = 0.05      # weighted fouls+cards/action at which control bottoms out
MIN_DRIBBLES = 5           # take-ons needed before pressure_resistance is meaningful

# Indices that the on-ball event stream cannot support, with the honest reason.
ABSTAINED_ALWAYS = {
    "leadership_index":
        "requires captaincy / communication / on-field leadership signals not "
        "present in event data",
    "recovery_behavior":
        "requires defensive actions (tackles, interceptions, pressures) not in "
        "the normalized event set",
    "tactical_discipline":
        "requires positional role-adherence or pressing data not reliably "
        "derivable from on-ball events",
}


def _clamp(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)


def _player_events(events, player_id: str) -> list:
    return [e for e in events if getattr(e, "player_id", None) == player_id]


def decision_stability(profile: dict) -> Optional[float]:
    """Ball retention as a proxy for decision quality: high completion, few losses.

    Needs ``pass_accuracy`` and ``turnover_rate``; abstains without them.
    """
    if profile.get("pass_accuracy") is None or profile.get("turnover_rate") is None:
        return None
    keep = 1.0 - min(1.0, profile["turnover_rate"] / REF_TURNOVER)
    return _clamp(0.6 * profile["pass_accuracy"] + 0.4 * keep)


def pressure_resistance(profile: dict) -> Optional[float]:
    """Take-on success — keeping the ball against a direct opponent.

    Abstains when there are too few dribbles to read (``MIN_DRIBBLES``).
    """
    if profile.get("dribbles", 0) < MIN_DRIBBLES or profile.get("dribble_success") is None:
        return None
    return _clamp(profile["dribble_success"])


def aggression_control(events, player_id: str, actions: Optional[int] = None
                       ) -> Optional[float]:
    """Disciplinary restraint: 1 down-weighted by fouls and cards per action.

    Needs the player's events; abstains without them or without an action count.
    """
    evs = _player_events(events, player_id)
    if not evs:
        return None
    fouls = sum(1 for e in evs if e.type == "foul")
    yellows = sum(1 for e in evs if e.type == "yellow_card")
    reds = sum(1 for e in evs if e.type == "red_card")
    n = actions if actions else len(evs)
    if n <= 0:
        return None
    rate = (fouls + 2 * yellows + 3 * reds) / n
    return _clamp(1.0 - min(1.0, rate / REF_DISCIPLINE))


def resilience_index(events, player_id: str, conceded_minutes) -> Optional[float]:
    """Does the player stay involved after the team concedes?

    Compares the player's action rate after the first goal conceded to the rate
    before it; a ratio at or above parity reads as resilient. Abstains without
    events, without a conceded goal, or with no activity before it to compare to.
    """
    if not conceded_minutes:
        return None
    evs = _player_events(events, player_id)
    if not evs:
        return None
    first = min(conceded_minutes)
    end = max((e.minute for e in evs), default=first)
    before_t = max(first, 1e-9)
    after_t = max(end - first, 1e-9)
    before = sum(1 for e in evs if e.minute < first)
    after = sum(1 for e in evs if e.minute >= first)
    if before == 0:
        return None
    rate_before = before / before_t
    rate_after = after / after_t
    if rate_before == 0:
        return None
    return _clamp(0.5 * (rate_after / rate_before))


def confidence_curve(events, player_id: str, window: float = 15.0) -> Optional[list]:
    """The player's involvement over the match, in fixed time windows.

    A descriptive series (actions per window), not an index — the shape of a
    player's game. Abstains without events.
    """
    evs = _player_events(events, player_id)
    if not evs:
        return None
    end = max(e.minute for e in evs)
    n_windows = int(end // window) + 1
    buckets = [0] * n_windows
    for e in evs:
        idx = min(int(e.minute // window), n_windows - 1)
        buckets[idx] += 1
    return [
        {"from": round(i * window, 1), "to": round((i + 1) * window, 1),
         "actions": buckets[i]}
        for i in range(n_windows)
    ]


def behavioral_profile(profile: dict, events=None, conceded_minutes=None) -> dict:
    """Every behavioral index for one player, with honest abstentions.

    ``profile`` is a built DNA profile (``fie.profiling.build_profile``) for the
    share-based indices; ``events`` (the player's, and the team's conceded
    minutes) unlock the discipline/timeline indices. Any index the data cannot
    support is ``None`` and listed under ``abstained`` with its reason — nothing
    is invented. Carries the profile's evidence-based ``confidence``.
    """
    player_id = profile.get("player_id")
    indices = {
        "decision_stability": decision_stability(profile),
        "pressure_resistance": pressure_resistance(profile),
        "aggression_control": (
            aggression_control(events, player_id, profile.get("actions"))
            if events is not None else None
        ),
        "resilience_index": (
            resilience_index(events, player_id, conceded_minutes)
            if events is not None else None
        ),
        "confidence_curve": (
            confidence_curve(events, player_id) if events is not None else None
        ),
    }
    abstained = dict(ABSTAINED_ALWAYS)
    for name, value in indices.items():
        if value is None and name not in abstained:
            abstained[name] = "insufficient data in the observed events"
    return {
        "player_id": player_id,
        **indices,
        "confidence": profile.get("confidence"),
        "abstained": abstained,
    }
