"""Live Mode (Application): the same engine, fed one observation at a time.

Historical replay hands the engine a finished event stream. Live Mode is the
mirror image: observations arrive one by one (in a real deployment, from a feed
through the fusion layer), and the Digital Twin's state is **corrected**
incrementally rather than recomputed from scratch. The wiring is the deferred
**event bus** (``fie.eventbus``), now triggered: each observation is published,
and the panel and Vision-Engine listeners update off the same event.

The engine stays leakage-safe by construction — the live panel at minute *t*
is computed from exactly the events received so far, so it is identical to the
batch panel over the same slice. That equality is the honest proof the streaming
path did not change the maths (tested).

Sessions live in memory (single worker; scale behind a shared store like the
metrics/rate-limit middleware). No persistence: a live session is ephemeral.
"""

from __future__ import annotations

from fie.eventbus import EventBus
from fie.events import Event
from fie.vision import estimate_positions

from .panel import panel_state
from .story import transition_beat

# In-process session registry (single worker). match_id -> LiveMatch.
_SESSIONS: dict = {}

# The true pre-kick-off reading: 0-0, balanced, no regime yet. Used as the first
# "previous state" so the opening goal / shift is detected without computing a
# panel at minute 0.
_BASELINE_PANEL = {
    "minute": 0, "score": {"home": 0, "away": 0}, "regime": "NORMAL",
    "momentum": {"home": 0.5, "away": 0.5},
}


class LiveMatch:
    """An in-progress match assembled from a stream of observations."""

    def __init__(self, match_id: str, home: str, away: str, params) -> None:
        self.match_id = match_id
        self.home = home
        self.away = away
        self.params = params
        self.events: list[Event] = []
        self.stream: list[dict] = []      # located observations for the Vision Engine
        self.minute = 0.0
        self.log: list[str] = []
        self.insights: list[dict] = []    # semantic beats detected live
        self._last_panel = _BASELINE_PANEL
        self.bus = EventBus()
        # The listeners: each reacts to the same published observation.
        self.bus.subscribe("observation", self._on_clock)
        self.bus.subscribe("observation", self._on_log)

    # -- listeners ---------------------------------------------------------- #
    def _on_clock(self, obs: dict) -> None:
        self.minute = max(self.minute, float(obs["minute"]))

    def _on_log(self, obs: dict) -> None:
        if obs["type"] in ("goal", "yellow_card", "red_card"):
            self.log.append(f"{int(obs['minute'])}' {obs['type']} — {obs['team']}")

    def tick(self, minute: float) -> None:
        """Advance the match clock (a live feed's clock moves between events)."""
        self.minute = max(self.minute, float(minute))

    # -- ingestion ---------------------------------------------------------- #
    def observe(self, obs: dict) -> dict:
        """Ingest one observation; return the freshly corrected live state.

        ``obs``: ``{minute, team (HOME/AWAY), type, x?, y?, player_id?, player?}``.
        """
        ev = Event(match_id=self.match_id, minute=float(obs["minute"]),
                   team=obs["team"], type=obs["type"],
                   player_id=obs.get("player_id"),
                   x=obs.get("x"), y=obs.get("y"))
        self.events.append(ev)
        self.events.sort(key=lambda e: e.minute)
        if obs.get("x") is not None and obs.get("y") is not None:
            self.stream.append({
                "t": float(obs["minute"]) * 60.0,
                "x": obs["x"], "y": obs["y"],
                "player_id": obs.get("player_id"),
                "player": obs.get("player"),
                "type": obs["type"], "team": obs["team"],
            })
            self.stream.sort(key=lambda i: i["t"])
        self.bus.publish("observation", obs)

        # Turn the raw observation stream into a live, semantic timeline: detect
        # the beat (goal / regime shift / momentum swing) this observation caused,
        # reusing the exact Match-Story kernel. Deterministic; nothing invented.
        panel = panel_state(self.events, self.minute, match_id=self.match_id,
                            params=self.params)
        beat = transition_beat(self._last_panel, panel, self.home, self.away)
        if beat is not None:
            self.insights.append(beat)
        self._last_panel = panel
        return self.snapshot()

    def snapshot(self) -> dict:
        """The live panel + estimated state at the current minute."""
        panel = panel_state(self.events, self.minute, match_id=self.match_id,
                            params=self.params)
        vision = estimate_positions(self.stream, self.minute * 60.0)
        return {
            "match_id": self.match_id,
            "home": self.home, "away": self.away,
            "minute": round(self.minute, 2),
            "n_events": len(self.events),
            "panel": panel,
            "vision": {"n_entities": len(vision), "entities": vision},
            "log": self.log[-8:],
            "insights": self.insights[-8:],
        }


def start(match_id: str, home: str, away: str, params) -> LiveMatch:
    session = LiveMatch(match_id, home, away, params)
    _SESSIONS[match_id] = session
    return session


def get(match_id: str) -> LiveMatch | None:
    return _SESSIONS.get(match_id)


def stop(match_id: str) -> None:
    _SESSIONS.pop(match_id, None)
