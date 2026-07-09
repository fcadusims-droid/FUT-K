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

import threading
from collections import Counter
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


def _base_key(minute, type_: str, team: str) -> tuple:
    """Dedup identity of one observation: (minute, type, team) — deliberately
    *without* the player, which providers fill in (or correct) between polls.
    Two events sharing a key are told apart by occurrence count, so a second
    goal in the same minute is a new event, not a duplicate."""
    return (round(float(minute), 3), type_, team)


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


# In-process memo of the rebuilt LiveMatch, keyed by match_id and validated
# against the stored log (prefix hash + params), so a poll that added two
# observations replays two — not the whole match. Purely an optimization: a
# cache miss falls back to the full deterministic replay, and any worker can
# still serve any session (the DB log remains the single source of truth).
_REBUILD_LOCK = threading.Lock()
_REBUILD_MEMO: dict[str, tuple] = {}  # match_id -> (params_key, n, prefix_hash, lm)


def _params_key(params) -> tuple:
    return (params.base_rate, params.tau, params.pressure_threshold,
            tuple(sorted(params.regime_scale.items())))


def _obs_fingerprint(o: dict) -> tuple:
    return (o["minute"], o["team"], o["type"], o["x"], o["y"],
            o["player_id"], o["player"])


def _forget(match_id: str) -> None:
    with _REBUILD_LOCK:
        _REBUILD_MEMO.pop(match_id, None)


def _rebuild_snapshot(db: Session, match_id: str, params) -> dict | None:
    """The live snapshot from the stored observation log (None if no session).

    Replaying in ``seq`` order reproduces the exact live state (deterministic),
    so this is what makes the session state portable across workers. The memo
    above only skips re-replaying a prefix this process has already replayed —
    verified by hash, so the result is identical to a cold rebuild.
    """
    row = db.get(LiveSession, match_id)
    if row is None:
        return None
    obs = _stored_observations(db, match_id)
    prints = [_obs_fingerprint(o) for o in obs]
    pkey = _params_key(params)
    with _REBUILD_LOCK:
        lm, replay_from = None, 0
        memo = _REBUILD_MEMO.get(match_id)
        if memo is not None:
            m_pkey, n, m_hash, m_lm = memo
            if (m_pkey == pkey and n <= len(prints)
                    and m_lm.home == row.home and m_lm.away == row.away
                    and m_hash == hash(tuple(prints[:n]))):
                lm, replay_from = m_lm, n
        if lm is None:
            lm = LiveMatch(match_id, row.home, row.away, params)
        for o in obs[replay_from:]:
            lm.observe(o)
        lm.tick(row.minute or 0.0)
        _REBUILD_MEMO[match_id] = (pkey, len(prints), hash(tuple(prints)), lm)
        return lm.snapshot()


def _append(db: Session, match_id: str, obs_list) -> int:
    """Persist observations not already logged. No commit.

    Idempotent by *occurrence count* per ``(minute, type, team)``: re-polling
    the same events feeds nothing, a genuinely new second event in the same
    minute (a quick brace) is fed, and a provider that fills in the scorer on
    a later poll does not re-feed the goal (the player is not part of the
    identity)."""
    existing = db.execute(
        select(LiveObservation).where(LiveObservation.match_id == match_id)
    ).scalars().all()
    stored = Counter(_base_key(r.minute, r.type, r.team) for r in existing)
    seen: Counter = Counter()
    seq = len(existing)
    fed = 0
    for o in obs_list:
        key = _base_key(o["minute"], o["type"], o["team"])
        seen[key] += 1
        if seen[key] <= stored[key]:
            continue  # this occurrence is already in the log
        db.add(LiveObservation(
            match_id=match_id, seq=seq, minute=float(o["minute"]),
            team=o["team"], type=o["type"], x=o.get("x"), y=o.get("y"),
            player_id=o.get("player_id"), player=o.get("player")))
        seq += 1
        fed += 1
    return fed


def start(db: Session, match_id: str, home: str, away: str, params) -> dict:
    """Open (or reset) a live session; returns the empty live snapshot."""
    _forget(match_id)
    db.execute(delete(LiveObservation).where(LiveObservation.match_id == match_id))
    row = db.get(LiveSession, match_id)
    if row is None:
        db.add(LiveSession(match_id=match_id, home=home, away=away, minute=0.0,
                           updated_at=_now()))
    else:
        row.home, row.away, row.minute, row.updated_at = home, away, 0.0, _now()
    db.commit()
    return _rebuild_snapshot(db, match_id, params)


def observe(db: Session, match_id: str, obs: dict, params) -> dict | None:
    """Ingest one observation and return the corrected state (None if no session)."""
    row = db.get(LiveSession, match_id)
    if row is None:
        return None
    _append(db, match_id, [obs])
    row.minute = max(row.minute or 0.0, float(obs["minute"]))
    row.updated_at = _now()
    db.commit()
    return _rebuild_snapshot(db, match_id, params)


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
    return fed, _rebuild_snapshot(db, match_id, params)


def state(db: Session, match_id: str, params) -> dict | None:
    """The live snapshot rebuilt from the store (None if no session)."""
    return _rebuild_snapshot(db, match_id, params)


def stop(db: Session, match_id: str) -> None:
    """End a live session: drop its log and marker."""
    _forget(match_id)
    db.execute(delete(LiveObservation).where(LiveObservation.match_id == match_id))
    row = db.get(LiveSession, match_id)
    if row is not None:
        db.delete(row)
    db.commit()
