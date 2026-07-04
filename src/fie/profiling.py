"""Individual Intelligence — player DNA from finished matches (Section 12).

Builds each player's behavioral profile by accumulating on-ball events across
finished matches, then derives rates/shares, a descriptive archetype, and a
normalized avatar. This is the "build profiles from finished matches first" path
of Section 12 — no live data required.

The accumulator shape is source-agnostic; connectors (e.g. StatsBomb) fill it.
Archetypes are *descriptive labels read from observed shares*, not ground truth —
treat them as hypotheses (Section 12's honest-data warning).
"""

from __future__ import annotations

from .players import avatar as _avatar

# Counter fields a connector accumulates per player.
COUNTER_FIELDS = (
    "actions",            # on-ball actions: passes + shots + dribbles + carries
    "passes",
    "passes_completed",
    "progressive",        # completed passes advancing >= PROGRESSIVE_MIN toward goal
    "key_passes",         # passes that set up a shot
    "assists",
    "shots",
    "goals",
    "dribbles",
    "dribbles_completed",
    "turnovers",          # dispossessed + miscontrol
)

# A completed pass is "progressive" if it advances the ball at least this far
# toward the opponent goal (StatsBomb 120-long pitch; the team always attacks +x).
PROGRESSIVE_MIN = 15.0

# Minimum on-ball actions before an archetype is assigned (else too little data).
MIN_ACTIONS = 60

# Reference ranges to normalize the avatar into [0, 1] for real football shares.
AVATAR_PROFILE_RANGES = {
    "pass_accuracy": (0.5, 1.0),
    "progressive_pass": (0.0, 0.4),
    "shot_frequency": (0.0, 0.15),
    "assist_frequency": (0.0, 0.10),
    "turnover_rate": (0.0, 0.10),
}


def new_record(player_id, name=None, team=None, position=None) -> dict:
    """A fresh per-player accumulator record.

    Beyond the on-ball counters it carries provenance: ``matches`` (how many
    matches have contributed to this record) and ``sources`` (which datasets),
    so a built profile can state how much real evidence — and from where — backs
    it. Nothing here is ever inferred; the fields are filled only as real events
    from real sources arrive.
    """
    rec = {"player_id": str(player_id), "name": name, "team": team, "position": position}
    rec.update({field: 0 for field in COUNTER_FIELDS})
    rec["matches"] = 0
    rec["sources"] = set()
    return rec


def profile_confidence(actions: int) -> float:
    """Reliability of a DNA profile from its evidence volume, in ``[0, 1)``.

    A saturating function of observed on-ball ``actions`` — the project's stated
    reliability measure (Section 12): more real evidence means more confidence,
    but never certainty. Anchored to ``MIN_ACTIONS`` so confidence crosses 0.5
    exactly at the volume where an archetype first becomes assignable::

        actions=0    -> 0.0     (no evidence)
        actions=60   -> 0.5     (= MIN_ACTIONS, the archetype threshold)
        actions=180  -> 0.75
        actions=540  -> 0.9

    This is a measurement of how much data supports the profile, not an estimate
    of anything about the player — it fabricates nothing.
    """
    a = max(0, int(actions))
    return round(a / (a + MIN_ACTIONS), 3)


def _safe(a, b):
    return a / b if b else 0.0


def real_archetype(profile: dict) -> str:
    """Descriptive archetype from observed shares (real-football thresholds).

    Order matters; the first matching rule wins. Thresholds are heuristics tuned
    to real event data, documented so they can be pinned by a test.
    """
    if profile["actions"] < MIN_ACTIONS:
        return "insufficient_data"
    if profile["shot_share"] >= 0.05 and profile["shots"] >= 6:
        return "finisher"
    if profile["key_pass_rate"] >= 0.035 or profile["assists"] >= 3:
        return "creator"
    if (
        profile["turnover_rate"] >= 0.04
        and profile["dribbles"] >= 10
        and profile["dribble_success"] < 0.6
    ):
        return "impulsive"
    if profile["pass_accuracy"] >= 0.85 and profile["shot_share"] < 0.02:
        return "conservative"
    return "balanced"


def profile_avatar(profile: dict) -> dict:
    """Normalized [0,1] avatar vector, via the validated players.avatar()."""
    avatar_input = {
        "pass_accuracy": profile["pass_accuracy"],
        "progressive_pass": profile["progressive_pass_share"],
        "shot_frequency": profile["shot_share"],
        "assist_frequency": profile["key_pass_rate"],
        "turnover_rate": profile["turnover_rate"],
    }
    return _avatar(avatar_input, ranges=AVATAR_PROFILE_RANGES)


def build_profile(record: dict) -> dict:
    """Derive a player's DNA profile from an accumulated counter record."""
    passes = record["passes"]
    completed = record["passes_completed"]
    actions = record["actions"]
    profile = {
        "player_id": record["player_id"],
        "name": record.get("name"),
        "team": record.get("team"),
        "position": record.get("position"),
        "actions": actions,
        "passes": passes,
        "shots": record["shots"],
        "goals": record["goals"],
        "assists": record["assists"],
        "dribbles": record["dribbles"],
        "pass_accuracy": _safe(completed, passes),
        "progressive_pass_share": _safe(record["progressive"], completed),
        "key_pass_rate": _safe(record["key_passes"], passes),
        "shot_share": _safe(record["shots"], actions),
        "turnover_rate": _safe(record["turnovers"], actions),
        "dribble_success": _safe(record["dribbles_completed"], record["dribbles"]),
    }
    profile["archetype"] = real_archetype(profile)
    profile["avatar"] = profile_avatar(profile)
    # Provenance + evidence-based reliability (never fabricated): how much real
    # data backs this profile, from which sources, and the derived confidence.
    profile["matches"] = int(record.get("matches", 0))
    profile["sources"] = sorted(record.get("sources") or ())
    profile["confidence"] = profile_confidence(actions)
    return profile


def build_profiles(table: dict) -> list:
    """Build every player's profile from an accumulator table, most active first."""
    profiles = [build_profile(rec) for rec in table.values()]
    profiles.sort(key=lambda p: p["actions"], reverse=True)
    return profiles
