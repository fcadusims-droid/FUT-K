"""FastAPI entrypoint — replay + prediction API (Phase B).

Every state endpoint recomputes the panel from the persisted event stream via
the validated ``fie`` engine, slicing events at the requested minute first —
the same leakage-safe discipline as ``backtest()`` (T-20-04).
"""

from __future__ import annotations

import math

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .insights import PRESETS, run_query
from .network import DEFAULT_CACHE, network_payload
from .models import Match, MatchEvent, PlayerProfile
from .panel import _row_to_event, panel_state
from .story import humanize_panel, match_story

app = FastAPI(
    title="Football Intelligence Engine API",
    version="0.2.0",
    description=(
        "Historical-replay API over the validated FIE engine: match state, "
        "regime, predictions with confidence, and the explained 'why' at any "
        "minute of an ingested match (Section 22 of the design document)."
    ),
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/matches")
def list_matches(
    competition: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(Match)
    if competition:
        stmt = stmt.where(Match.competition == competition)
    rows = db.execute(stmt.order_by(Match.match_date, Match.id)).scalars().all()
    return [
        {
            "id": m.id,
            "competition": m.competition,
            "season": m.season,
            "match_date": m.match_date,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "home_goals_final": m.home_goals_final,
            "away_goals_final": m.away_goals_final,
        }
        for m in rows
    ]


def _get_match(db: Session, match_id: str) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"match {match_id} not found")
    return match


def _load_events(db: Session, match_id: str):
    rows = db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == match_id)
        .order_by(MatchEvent.minute)
    ).scalars().all()
    return [_row_to_event(r) for r in rows]


@app.get("/matches/{match_id}")
def match_detail(match_id: str, db: Session = Depends(get_db)) -> dict:
    m = _get_match(db, match_id)
    events = _load_events(db, match_id)
    duration = max((e.minute for e in events), default=90.0)
    return {
        "id": m.id,
        "competition": m.competition,
        "season": m.season,
        "match_date": m.match_date,
        "home_team": m.home_team,
        "away_team": m.away_team,
        "home_goals_final": m.home_goals_final,
        "away_goals_final": m.away_goals_final,
        "n_events": len(events),
        "duration": duration,
        "goal_minutes": [
            {"minute": e.minute, "team": e.team} for e in events if e.type == "goal"
        ],
    }


@app.get("/matches/{match_id}/state")
def match_state(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    db: Session = Depends(get_db),
) -> dict:
    """The intelligent panel (Section 22) at one minute of the match."""
    _get_match(db, match_id)
    events = _load_events(db, match_id)
    return panel_state(events, minute, match_id=match_id)


@app.get("/matches/{match_id}/timeline")
def match_timeline(
    match_id: str,
    step: int = Query(5, ge=1, le=15),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Panel states across the whole match — the replay scrubber's data."""
    _get_match(db, match_id)
    events = _load_events(db, match_id)
    duration = int(max((e.minute for e in events), default=90.0))
    return [
        panel_state(events, float(minute), match_id=match_id)
        for minute in range(step, duration + 1, step)
    ]


@app.get("/matches/{match_id}/state/human")
def match_state_human(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    db: Session = Depends(get_db),
) -> dict:
    """The panel in plain language (product level 3) + the raw panel."""
    m = _get_match(db, match_id)
    events = _load_events(db, match_id)
    panel = panel_state(events, minute, match_id=match_id)
    return {
        "human": humanize_panel(panel, m.home_team or "HOME", m.away_team or "AWAY"),
        "panel": panel,
    }


@app.get("/matches/{match_id}/story")
def match_story_endpoint(match_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """The narrated Match Story (product level 4 / design-doc Section 17)."""
    m = _get_match(db, match_id)
    events = _load_events(db, match_id)
    duration = math.ceil(max((e.minute for e in events), default=90.0))
    timeline = [
        panel_state(events, float(t), match_id=match_id)
        for t in range(1, duration + 1)
    ]
    goal_minutes = [{"minute": e.minute, "team": e.team} for e in events if e.type == "goal"]
    return match_story(timeline, goal_minutes, m.home_team or "HOME", m.away_team or "AWAY")


@app.get("/matches/{match_id}/network")
def match_network(
    match_id: str,
    side: str = Query("HOME", pattern="^(HOME|AWAY)$"),
    db: Session = Depends(get_db),
) -> dict:
    """The team's passing network for this match (Section 12, Layer 5)."""
    m = _get_match(db, match_id)
    team_name = m.home_team if side == "HOME" else m.away_team
    try:
        from fie.sources.statsbomb import fetch_events

        raw = fetch_events(match_id, cache_dir=DEFAULT_CACHE)
    except Exception as exc:  # noqa: BLE001 - cache miss + no network
        raise HTTPException(status_code=503,
                            detail=f"raw event data unavailable: {exc}") from exc
    payload = network_payload(raw, team_name or side)
    payload["side"] = side
    return payload


@app.get("/insights/presets")
def insights_presets() -> dict:
    return PRESETS


@app.get("/insights/{query}")
def insights(query: str, team: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    """Historical query bank (product level 6): football, not just games."""
    try:
        return run_query(db, query, team=team)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/players/profiles")
def player_profiles(
    team: str | None = None,
    archetype: str | None = None,
    min_actions: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(PlayerProfile)
    if team:
        stmt = stmt.where(PlayerProfile.team == team)
    if archetype:
        stmt = stmt.where(PlayerProfile.archetype == archetype)
    if min_actions:
        stmt = stmt.where(PlayerProfile.actions >= min_actions)
    rows = db.execute(stmt.order_by(PlayerProfile.actions.desc())).scalars().all()
    return [
        {
            "player_id": p.player_id,
            "name": p.name,
            "team": p.team,
            "position": p.position,
            "actions": p.actions,
            "goals": p.goals,
            "assists": p.assists,
            "pass_accuracy": p.pass_accuracy,
            "key_pass_rate": p.key_pass_rate,
            "shot_share": p.shot_share,
            "archetype": p.archetype,
        }
        for p in rows
    ]
