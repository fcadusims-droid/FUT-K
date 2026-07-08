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

**State lives in the database, not the process.** A live session is just its
ordered log of observations (``live_observations``); the panel, vision, log and
insights are a deterministic function of that log, rebuilt on demand. So any
worker can serve any live match — the horizontal-scale/edge prerequisite. The
in-memory ``LiveMatch`` remains the (pure, testable) compute object the store
rebuilds; it just no longer *is* the session.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fie.eventbus import EventBus
from fie.events import Event
from fie.vision import estimate_positions

from .models import LiveObservation, LiveSession
from .panel import panel_state
from .story import transition_beat

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


# --------------------------------------------------------------------------- #
# DB-backed session store — stateless compute, any worker serves any match
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _obs_key(o: dict) -> tuple:
    return (round(float(o["minute"]), 3), o["type"], o["team"], o.get("player_id"))


def exists(db: Session, match_id: str) -> bool:
    return db.get(LiveSession, match_id) is not None


def _stored_observations(db: Session, match_id: str) -> list[dict]:
    rows = db.execute(
        select(LiveObservation)
        .where(LiveObservation.match_id == match_id)
        .order_by(LiveObservation.seq)
    ).scalars().all()
    return [
        {"minute": r.minute, "team": r.team, "type": r.type, "x": r.x, "y": r.y,
         "player_id": r.player_id, "player": r.player}
        for r in rows
    ]


def _rebuild(db: Session, match_id: str, params) -> LiveMatch | None:
    """Rebuild the transient LiveMatch by replaying the stored observation log.

    Replaying in ``seq`` order reproduces the exact live state (deterministic),
    so this is what makes the session state portable across workers.
    """
    row = db.get(LiveSession, match_id)
    if row is None:
        return None
    lm = LiveMatch(match_id, row.home, row.away, params)
    for obs in _stored_observations(db, match_id):
        lm.observe(obs)
    lm.tick(row.minute or 0.0)
    return lm


def _append(db: Session, match_id: str, obs_list) -> int:
    """Persist observations not already logged (idempotent by key). No commit."""
    existing = db.execute(
        select(LiveObservation).where(LiveObservation.match_id == match_id)
    ).scalars().all()
    seen = {_obs_key({"minute": r.minute, "type": r.type, "team": r.team,
                      "player_id": r.player_id}) for r in existing}
    seq = len(existing)
    fed = 0
    for o in obs_list:
        if _obs_key(o) in seen:
            continue
        db.add(LiveObservation(
            match_id=match_id, seq=seq, minute=float(o["minute"]),
            team=o["team"], type=o["type"], x=o.get("x"), y=o.get("y"),
            player_id=o.get("player_id"), player=o.get("player")))
        seen.add(_obs_key(o))
        seq += 1
        fed += 1
    return fed


def start(db: Session, match_id: str, home: str, away: str, params) -> dict:
    """Open (or reset) a live session; returns the empty live snapshot."""
    db.execute(delete(LiveObservation).where(LiveObservation.match_id == match_id))
    row = db.get(LiveSession, match_id)
    if row is None:
        db.add(LiveSession(match_id=match_id, home=home, away=away, minute=0.0,
                           updated_at=_now()))
    else:
        row.home, row.away, row.minute, row.updated_at = home, away, 0.0, _now()
    db.commit()
    return _rebuild(db, match_id, params).snapshot()


def observe(db: Session, match_id: str, obs: dict, params) -> dict | None:
    """Ingest one observation and return the corrected state (None if no session)."""
    row = db.get(LiveSession, match_id)
    if row is None:
        return None
    _append(db, match_id, [obs])
    row.minute = max(row.minute or 0.0, float(obs["minute"]))
    row.updated_at = _now()
    db.commit()
    return _rebuild(db, match_id, params).snapshot()


def feed(db: Session, match_id: str, obs_list, params, *,
         tick_minute: float | None = None):
    """Ingest a batch of observations (deduped); advance the clock. (fed, snapshot).

    Returns None when no session exists. Used by the live feed connector glue.
    """
    row = db.get(LiveSession, match_id)
    if row is None:
        return None
    fed = _append(db, match_id, obs_list)
    minute = row.minute or 0.0
    for o in obs_list:
        minute = max(minute, float(o["minute"]))
    if tick_minute is not None:
        minute = max(minute, float(tick_minute))
    row.minute = minute
    row.updated_at = _now()
    db.commit()
    return fed, _rebuild(db, match_id, params).snapshot()


def state(db: Session, match_id: str, params) -> dict | None:
    """The live snapshot rebuilt from the store (None if no session)."""
    lm = _rebuild(db, match_id, params)
    return lm.snapshot() if lm is not None else None


def stop(db: Session, match_id: str) -> None:
    """End a live session: drop its log and marker."""
    db.execute(delete(LiveObservation).where(LiveObservation.match_id == match_id))
    row = db.get(LiveSession, match_id)
    if row is not None:
        db.delete(row)
    db.commit()
