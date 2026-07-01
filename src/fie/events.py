"""Data layer and the normalized event model (Section 5).

Regardless of source, everything becomes an ``Event`` in one format. The player
and position fields are optional — filled only when the source provides them.
``State`` is the minimal contextual snapshot (score + minute) the downstream
modules read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# The normalized event types the engine understands. Sources may emit others;
# unknown types simply carry zero offensive weight (see indices.EVENT_WEIGHT).
EVENT_TYPES = {
    "shot",
    "shot_on_target",
    "dangerous_attack",
    "corner",
    "foul",
    "yellow_card",
    "red_card",
    "goal",
    "pass",
    "dribble",
    "reception",
}


@dataclass
class Event:
    """A single normalized match event (Section 5)."""

    match_id: str
    minute: float
    team: str  # "HOME" | "AWAY"
    type: str
    player_id: Optional[str] = None
    target_id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    xg: Optional[float] = None


@dataclass
class State:
    """Contextual state of the match at a given minute (score, time)."""

    match_id: str = ""
    minute: float = 0.0
    home_goals: int = 0
    away_goals: int = 0

    def goal_diff(self, team: str) -> int:
        """Goal difference from ``team``'s point of view (positive == leading)."""
        if team == "HOME":
            return self.home_goals - self.away_goals
        return self.away_goals - self.home_goals


def state_from_events(match_id: str, events, minute: float) -> State:
    """Build the ``State`` at ``minute`` by counting only goals up to ``minute``.

    This is a leakage-safe constructor: it never looks past ``minute`` (see the
    T-20-04 leakage discipline).
    """
    home = sum(1 for e in events if e.type == "goal" and e.team == "HOME" and e.minute <= minute)
    away = sum(1 for e in events if e.type == "goal" and e.team == "AWAY" and e.minute <= minute)
    return State(match_id=match_id, minute=minute, home_goals=home, away_goals=away)
