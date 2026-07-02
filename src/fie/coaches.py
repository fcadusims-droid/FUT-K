"""Coach Intelligence (Section 13).

Coaches have patterns too. Modelling them gives the prediction engine hints about
what tends to happen to a team's structure. Use the profiles as weak
probabilities, not laws.
"""

from __future__ import annotations

# Re-exported from the core: the adjustment is a lambda multiplier, so it lives
# in fie.prediction; the Knowledge-layer surface (and tests T-13-04/05) keep
# importing it from here.
from .prediction import coach_adjustment

__all__ = ["coach_profile", "coach_adjustment", "coaching_philosophy"]


def coach_profile(coach_matches, *, tactical_tendency=None,
                  substitution_pattern=None, post_event_pattern=None) -> dict:
    """Assemble a coach profile by score context, subs, and reactions.

    The three analysers are injectable so the profile can be built from whatever
    match summariser is available; each defaults to a no-op returning ``None``.
    """
    tactical_tendency = tactical_tendency or (lambda m, ctx: None)
    substitution_pattern = substitution_pattern or (lambda m: None)
    post_event_pattern = post_event_pattern or (lambda m: None)

    profile = {
        ctx: tactical_tendency(coach_matches, ctx)
        for ctx in ("winning", "losing", "drawing")
    }
    profile["subs"] = substitution_pattern(coach_matches)
    profile["reaction"] = post_event_pattern(coach_matches)
    return profile


def coaching_philosophy(profile: dict) -> str:
    """A stable identity label, the default when matchup data is scarce."""
    if profile.get("losing") == "press" and profile.get("winning") == "hold":
        return "OFFENSIVE"
    if profile.get("losing") == "hold" and profile.get("winning") == "retreat":
        return "PRAGMATIC"
    return "BALANCED"
