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
from .ask import answer as ask_answer
from .benchmarks import BENCHMARKS
from .evolution import team_evolution
from .insights import PRESETS, run_query
from .learningloop import get_active_params
from .models import ModelVersion
from .similarity import match_vector, similar_matches
from .network import DEFAULT_CACHE, network_payload
from .models import Match, MatchEvent, PlayerProfile
from .observability import MetricsMiddleware, metrics
from .security import SecurityMiddleware
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


# Middleware order: metrics outermost (times everything, incl. 401/429).
app.add_middleware(SecurityMiddleware)
app.add_middleware(MetricsMiddleware)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics_json() -> dict:
    """Observability (level 15): per-route counts, errors, latency."""
    return metrics.snapshot()


@app.get("/metrics/prometheus")
def metrics_prom():
    from starlette.responses import PlainTextResponse

    return PlainTextResponse(metrics.prometheus())


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
    return panel_state(events, minute, match_id=match_id, params=get_active_params(db))


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
        panel_state(events, float(minute), match_id=match_id, params=get_active_params(db))
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
    panel = panel_state(events, minute, match_id=match_id, params=get_active_params(db))
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
        panel_state(events, float(t), match_id=match_id, params=get_active_params(db))
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


@app.get("/matches/{match_id}/similar")
def similar(match_id: str, limit: int = Query(5, ge=1, le=20),
            db: Session = Depends(get_db)) -> list[dict]:
    """Semantic search (level 7): matches whose dynamics felt like this one."""
    _get_match(db, match_id)
    all_matches = db.execute(select(Match)).scalars().all()
    vectors = {}
    for m in all_matches:
        evs = _load_events(db, m.id)
        if evs:
            vectors[m.id] = match_vector(evs)
    if match_id not in vectors:
        raise HTTPException(status_code=404, detail="no events for this match")
    target = vectors.pop(match_id)
    by_id = {m.id: m for m in all_matches}
    return [
        {
            "id": mid, "similarity": round(sim, 3),
            "home_team": by_id[mid].home_team, "away_team": by_id[mid].away_team,
            "match_date": by_id[mid].match_date,
            "final": f"{by_id[mid].home_goals_final}-{by_id[mid].away_goals_final}",
        }
        for mid, sim in similar_matches(target, vectors, limit)
    ]


def _ask_context(db: Session, match_id: str) -> dict:
    m = _get_match(db, match_id)
    events = _load_events(db, match_id)
    duration = math.ceil(max((e.minute for e in events), default=90.0))
    timeline = [panel_state(events, float(t), match_id=match_id, params=get_active_params(db))
                for t in range(1, duration + 1)]
    goal_minutes = [{"minute": e.minute, "team": e.team}
                    for e in events if e.type == "goal"]
    story = match_story(timeline, goal_minutes, m.home_team or "HOME",
                        m.away_team or "AWAY")
    return {
        "home": m.home_team or "HOME", "away": m.away_team or "AWAY",
        "story": story, "events": events,
        "final": (m.home_goals_final or 0, m.away_goals_final or 0),
        "timeline_last": timeline[-1],
    }


@app.get("/matches/{match_id}/ask")
def ask(match_id: str, q: str = Query(..., min_length=2),
        db: Session = Depends(get_db)) -> dict:
    """Conversational layer (level 8): deterministic Q&A over the engine."""
    return ask_answer(q, _ask_context(db, match_id))


@app.get("/teams/{team}/evolution")
def evolution(team: str, competition: str | None = None,
              db: Session = Depends(get_db)) -> dict:
    """Team memory (level 9): month-by-month evolution across the season."""
    return team_evolution(db, team, competition)


@app.get("/matches/{match_id}/explain")
def explain_endpoint(match_id: str, minute: float = Query(..., ge=0, le=150),
                     db: Session = Depends(get_db)) -> dict:
    """Structured explainability cascade (level 10): claim -> because ->
    evidence -> reliability."""
    _get_match(db, match_id)
    events = _load_events(db, match_id)
    panel = panel_state(events, minute, match_id=match_id, params=get_active_params(db))
    because = panel["explanation"]["because"]
    return {
        "claim": panel["explanation"]["claim"],
        "probability": panel["predictions"]["goal_next_10min"],
        "because": because,
        "evidence": {
            # The engine inputs feeding this claim (documented, honest count):
            # momentum, pressure x2, regime, score, minute, cards, recent shots.
            "metrics_used": 8,
            "mechanisms_found": len(because),
        },
        "reliability": panel["confidence"],
    }


@app.get("/model/versions")
def model_versions(db: Session = Depends(get_db)) -> list[dict]:
    """The learning loop's version history (level 19). The latest promoted
    version is what the panel currently serves."""
    rows = db.execute(select(ModelVersion).order_by(ModelVersion.id.desc())).scalars().all()
    return [
        {"id": v.id, "created_at": v.created_at, "competition": v.competition,
         "base_rate": v.base_rate, "tau": v.tau,
         "holdout_log_loss": v.holdout_log_loss,
         "baseline_log_loss": v.baseline_log_loss,
         "promoted": v.promoted, "note": v.note}
        for v in rows
    ]


@app.get("/benchmarks")
def benchmarks() -> list[dict]:
    """Public benchmark (level 11): validated numbers + how to reproduce them."""
    return BENCHMARKS


@app.get("/search")
def search(q: str = Query(..., min_length=2), db: Session = Depends(get_db)) -> list[dict]:
    """Product API (level 12): free-text match search by team name."""
    needle = q.lower()
    rows = db.execute(select(Match)).scalars().all()
    out = [
        {"id": m.id, "match_date": m.match_date, "home_team": m.home_team,
         "away_team": m.away_team,
         "final": f"{m.home_goals_final}-{m.away_goals_final}"}
        for m in rows
        if needle in (m.home_team or "").lower() or needle in (m.away_team or "").lower()
    ]
    out.sort(key=lambda r: r["match_date"] or "", reverse=True)
    return out[:25]


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
