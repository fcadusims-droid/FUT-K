"""Phase A2 — multi-competition ingestion pipeline.

Populates the production schema (matches, events, player_profiles) from
StatsBomb open data via the validated `fie` engine and connector. Idempotent:
re-ingesting a competition replaces its rows rather than duplicating them, so
the pipeline is safe to re-run as more data becomes available (Phase A3).
"""

from __future__ import annotations

import hashlib

from sqlalchemy import delete
from sqlalchemy.orm import Session

from fie.profiling import build_profiles
from fie.sources.statsbomb import StatsBombSource

from .models import Match, MatchEvent, PlayerProfile


def ingest_match(session: Session, source: StatsBombSource, match_id) -> str:
    """Upsert one match and replace its events. Returns the match id (str).

    ``events_hash`` records data provenance: a deterministic digest of the
    normalized event stream, so any experiment can state exactly which data
    produced it (audit level 18 / data versioning).
    """
    match = source.match(match_id)
    mid = match["match_id"]
    digest = hashlib.sha256(
        "|".join(f"{e.minute:.3f},{e.team},{e.type},{e.player_id}"
                 for e in match["events"]).encode()
    ).hexdigest()[:16]

    session.merge(
        Match(
            id=mid,
            competition=str(source.competition_id),
            season=str(source.season_id),
            match_date=match.get("match_date"),
            home_team=match["home_team"],
            away_team=match["away_team"],
            status="finished",
            home_goals_final=match.get("home_score"),
            events_hash=digest,
            away_goals_final=match.get("away_score"),
        )
    )
    session.execute(delete(MatchEvent).where(MatchEvent.match_id == mid))
    session.add_all(
        MatchEvent(
            match_id=mid, minute=e.minute, team=e.team, type=e.type,
            player_id=e.player_id, target_id=e.target_id, x=e.x, y=e.y, xg=e.xg,
        )
        for e in match["events"]
    )
    return mid


def _upsert_profiles(session: Session, profiles: list[dict]) -> None:
    for p in profiles:
        session.merge(
            PlayerProfile(
                player_id=p["player_id"], name=p["name"], team=p["team"],
                position=p["position"], actions=p["actions"], passes=p["passes"],
                shots=p["shots"], goals=p["goals"], assists=p["assists"],
                pass_accuracy=p["pass_accuracy"],
                progressive_pass=p["progressive_pass_share"],
                key_pass_rate=p["key_pass_rate"], shot_share=p["shot_share"],
                turnover_rate=p["turnover_rate"], archetype=p["archetype"],
            )
        )


def ingest_competition(
    session: Session,
    competition_id: int,
    season_id: int,
    cache_dir: str | None = None,
    limit: int | None = None,
    source: StatsBombSource | None = None,
) -> dict:
    """Ingest matches, events, and player profiles for one competition/season.

    ``source`` is injectable (offline tests pass one with fixture loaders);
    otherwise a real ``StatsBombSource`` is built from ``competition_id``/
    ``season_id``/``cache_dir``.
    """
    source = source or StatsBombSource(competition_id, season_id, cache_dir=cache_dir)
    raw_matches = sorted(source.matches(), key=lambda m: m.get("match_date") or "")
    if limit:
        raw_matches = raw_matches[:limit]

    table: dict = {}
    ingested, skipped = [], []
    for raw in raw_matches:
        mid = raw["match_id"]
        try:
            ingested.append(ingest_match(session, source, mid))
            source.player_stats(mid, table)
        except Exception as exc:  # noqa: BLE001 - keep the pipeline going
            skipped.append((mid, str(exc)))
    session.commit()

    profiles = build_profiles(table)
    _upsert_profiles(session, profiles)
    session.commit()

    return {
        "competition_id": competition_id, "season_id": season_id,
        "ingested": ingested, "skipped": skipped, "profiles": len(profiles),
    }
