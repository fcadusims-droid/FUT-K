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
import os as _os

from fie.plugins import load_plugins as _load_plugins, run_all as _run_plugins

# Plugin discovery (docs/ARCHITECTURE.md): repo-root plugins/ or FUTK_PLUGINS_DIR.
PLUGINS_DIR = _os.environ.get(
    "FUTK_PLUGINS_DIR",
    _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)))), "plugins"),
)
_load_plugins(PLUGINS_DIR)
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
        "events_hash": m.events_hash,
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


@app.get("/matches/{match_id}/events")
def match_events(match_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """The match's normalized events with pitch coordinates.

    Raw material for the 2D pitch replay: every persisted event (shots, goals,
    corners, cards, fouls) with its minute, team and engine 0-100 pitch
    location (the acting team's attacking frame) where recorded. Real
    touchpoints only — nothing interpolated server-side.
    """
    _get_match(db, match_id)
    rows = db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == match_id)
        .order_by(MatchEvent.minute, MatchEvent.id)
    ).scalars().all()
    # Player identity for click-through to Player DNA: one name lookup for
    # every distinct player involved in this match's events.
    ids = {r.player_id for r in rows if r.player_id}
    names = {}
    if ids:
        names = {
            p.player_id: p.name
            for p in db.execute(
                select(PlayerProfile).where(PlayerProfile.player_id.in_(ids))
            ).scalars()
        }
    return [
        {"minute": r.minute, "type": r.type, "team": r.team,
         "x": r.x, "y": r.y, "xg": r.xg,
         "player_id": r.player_id,
         "player": names.get(r.player_id)}
        for r in rows
    ]


@app.get("/matches/{match_id}/replay2d")
def replay2d(match_id: str, db: Session = Depends(get_db)) -> dict:
    """The Digital Match Twin's dense on-ball stream.

    Every pass, carry and shot with real start+end pitch locations, real
    sub-second timestamps and durations, plus point actions (receipts,
    recoveries, duels...). This is what the 2D pitch animates — provider
    truth, not simulation. 404 when no stream exists and the raw cache is
    unavailable; the UI then falls back to the sparse normalized events.
    """
    from .twin import get_stream

    m = _get_match(db, match_id)
    stream = get_stream(db, m)
    if stream is None:
        raise HTTPException(
            status_code=404,
            detail="no twin stream for this match (raw event cache unavailable)",
        )
    return stream


@app.get("/matches/{match_id}/simulate")
def simulate(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    n_sims: int = Query(10000, ge=100, le=50000),
    seed: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """Future Simulation Engine: thousands of futures from this minute.

    Runs ``n_sims`` seeded Monte-Carlo forward simulations of the remaining
    match from the calibrated goal rates, bounded by the match's **real**
    remaining time (derived from the twin stream / period markers — never a
    hardcoded 90). Returns the outcome distribution and per-lane opportunity
    windows. Deterministic given ``seed``.
    """
    from fie.events import state_from_events
    from fie.regime import detect_regime
    from fie.simulation import simulate_forward

    from .twin import real_duration_minutes

    m = _get_match(db, match_id)
    events = _load_events(db, match_id)
    duration = real_duration_minutes(db, m)
    if duration is None:
        duration = max((e.minute for e in events), default=90.0)
    horizon = max(0.0, duration - minute)

    params = get_active_params(db)
    state = state_from_events(match_id, events, minute)
    events_until = [e for e in events if e.minute <= minute]
    regime = detect_regime(state, events_until, params)
    result = simulate_forward(
        state, events, params, horizon_minutes=horizon,
        n_sims=n_sims, seed=seed, regime=regime,
    )
    result["real_duration"] = duration
    result["duration_source"] = "twin stream (real recorded final second)"
    return result


@app.get("/matches/{match_id}/vision")
def vision(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    evaluate: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """Vision Engine: the continuous estimated state of every entity.

    From the dense twin stream (real observations), returns each player's
    estimated position, velocity and **confidence** at ``minute`` — held from
    the last real touch, decaying with time unobserved, corrected whenever a
    real observation lands. With ``evaluate=true`` it also returns the engine's
    self-evaluation: how far its motion model predicted the next real touch,
    versus assuming the entity stayed put (the honest §5.10 finding).
    """
    from fie.vision import estimate_positions, evaluate_prediction

    from .twin import get_stream

    m = _get_match(db, match_id)
    stream = get_stream(db, m)
    if stream is None:
        raise HTTPException(status_code=404,
                            detail="no twin stream for this match")
    items = stream["items"]
    at = minute * 60.0
    entities = estimate_positions(items, at)
    payload = {
        "minute": round(minute, 2),
        "entities": entities,
        "n_entities": len(entities),
        "note": ("Positions held from each player's last real touch, confidence "
                 "decaying with time unobserved and reset on re-observation. On "
                 "sparse event data this static-hold is the validated-best "
                 "estimate; the kinematic model is ready for dense tracking "
                 "feeds."),
    }
    if evaluate:
        payload["self_evaluation"] = evaluate_prediction(items)
    return payload


@app.get("/matches/{match_id}/decisions")
def decisions(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    team: str = Query("HOME"),
    seed: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """Strategic Assistant: rank in-match approaches by win-probability delta.

    Re-simulates the remaining match (real data-bounded horizon) under each
    candidate approach and ranks them for ``team``. Deterministic given
    ``seed``; the payload states it is a model-based decision aid.
    """
    from fie.events import state_from_events
    from fie.regime import detect_regime
    from fie.strategy import evaluate_decisions

    from .twin import real_duration_minutes

    if team not in ("HOME", "AWAY"):
        raise HTTPException(status_code=422, detail="team must be HOME or AWAY")
    m = _get_match(db, match_id)
    events = _load_events(db, match_id)
    duration = real_duration_minutes(db, m)
    if duration is None:
        duration = max((e.minute for e in events), default=90.0)
    horizon = max(0.0, duration - minute)

    params = get_active_params(db)
    state = state_from_events(match_id, events, minute)
    events_until = [e for e in events if e.minute <= minute]
    regime = detect_regime(state, events_until, params)
    return evaluate_decisions(state, events, params, team=team,
                              horizon_minutes=horizon, seed=seed, regime=regime)


@app.get("/matches/{match_id}/tactics")
def tactics(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    db: Session = Depends(get_db),
) -> dict:
    """Intelligent-field geometry for the Visual Twin at one minute.

    Team block heights, corridor tendencies and territory from real event
    locations (`fie.tactical.tactical_geometry`), joined with the calibrated
    goal probability so the hottest lane can be drawn as an opportunity
    corridor. Leakage-safe: events are sliced at `minute` first.
    """
    from fie.tactical import tactical_geometry

    _get_match(db, match_id)
    events = _load_events(db, match_id)
    params = get_active_params(db)
    events_until = [e for e in events if e.minute <= minute]
    geo = tactical_geometry(events_until, minute, tau=params.tau)
    panel = panel_state(events, minute, match_id=match_id, params=params)
    geo["goal_next_10min"] = panel["predictions"]["goal_next_10min"]
    geo["momentum"] = panel["momentum"]
    return geo


@app.get("/matches/{match_id}/crosscheck")
def crosscheck(match_id: str, db: Session = Depends(get_db)) -> dict:
    """Multi-provider verification of this fixture's facts (the fusion layer).

    Resolves the match in `fused_matches` by canonical (date, home, away) and
    returns per-field agreement — the evidence that the reconstruction shown
    in the replay matches independent providers.
    """
    from fie.fusion import normalize_entity

    from .models import FusedMatchRecord

    m = _get_match(db, match_id)
    row = db.execute(
        select(FusedMatchRecord).where(
            FusedMatchRecord.match_date == (m.match_date or ""),
            FusedMatchRecord.home_team == normalize_entity(m.home_team or ""),
            FusedMatchRecord.away_team == normalize_entity(m.away_team or ""),
        )
    ).scalar_one_or_none()
    if row is None:
        return {"providers": 1, "verified": False,
                "note": "no independent provider fused for this fixture yet"}
    import json as _json

    fields = _json.loads(row.fields_json)
    agreed = sum(1 for f in fields.values() if f["agreed"] and f["sources"])
    compared = sum(1 for f in fields.values()
                   if len(f["sources"]) + len(f["dissent"]) >= 2)
    return {
        "providers": row.n_sources,
        "sources": row.sources.split(","),
        "verified": True,
        "fields_compared": compared,
        "fields_agreed": agreed,
        "conflicts": row.conflicts.split(",") if row.conflicts else [],
        "league": row.league,
    }


@app.get("/matches/{match_id}/whatif")
def whatif_endpoint(
    match_id: str,
    minute: float = Query(..., ge=0, le=150),
    type: str = Query(..., alias="type"),
    team: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """What If? (the fourth mode): remove one real event and re-run the engine.

    Returns baseline vs counterfactual panel series from the event's minute to
    full time. Purely deterministic — see the payload's honesty note.
    """
    from .whatif import REMOVABLE, whatif_remove

    if type not in REMOVABLE:
        raise HTTPException(status_code=422,
                            detail=f"type must be one of {sorted(REMOVABLE)}")
    if team not in ("HOME", "AWAY"):
        raise HTTPException(status_code=422, detail="team must be HOME or AWAY")
    _get_match(db, match_id)
    events = _load_events(db, match_id)
    result = whatif_remove(events, minute, type, team, match_id,
                           params=get_active_params(db))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"no {type} by {team} near minute {minute}",
        )
    return result


@app.get("/fusion/records")
def fusion_records(
    team: str | None = None,
    league: str | None = None,
    conflicts_only: bool = False,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Cross-provider fused match records (the Data Fusion Layer, persisted).

    Each record carries, per field, the fused value, its confidence, the
    winning sources and any recorded dissent — populated by
    ``scripts/ingest_fused.py``.
    """
    from .fusionstore import list_fused

    return list_fused(db, team=team, league=league,
                      conflicts_only=conflicts_only, limit=limit)


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


@app.get("/matches/{match_id}/plugins")
def match_plugins(match_id: str, db: Session = Depends(get_db)) -> dict:
    """Every registered plugin metric for this match (docs/ARCHITECTURE.md)."""
    _get_match(db, match_id)
    events = _load_events(db, match_id)
    return _run_plugins(events, get_active_params(db))


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
    player_id: str | None = None,
    min_actions: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(PlayerProfile)
    if player_id:
        stmt = stmt.where(PlayerProfile.player_id == player_id)
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
