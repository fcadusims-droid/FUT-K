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

from sqlalchemy import select

from fie.profiling import COUNTER_FIELDS, build_profile
from fie.sources.statsbomb import StatsBombSource

from .models import Match, MatchEvent, PlayerProfile, PlayerSeasonProfile


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
                matches=p.get("matches"), confidence=p.get("confidence"),
                sources=",".join(p.get("sources") or ()),
            )
        )


def _upsert_season_profiles(session: Session, table: dict,
                            competition: str, season: str) -> None:
    """Persist this ingest's accumulator as (player, competition, season) rows.

    Raw counters are stored (additive), so the global profile is always
    rebuildable as the exact sum of a player's season rows — the Player
    Evolution Timeline's storage primitive.
    """
    for rec in table.values():
        derived = build_profile(rec)
        session.merge(
            PlayerSeasonProfile(
                player_id=rec["player_id"], competition=competition, season=season,
                name=rec.get("name"), team=rec.get("team"),
                position=rec.get("position"),
                **{f: rec.get(f, 0) for f in COUNTER_FIELDS},
                pass_accuracy=derived["pass_accuracy"],
                progressive_pass=derived["progressive_pass_share"],
                key_pass_rate=derived["key_pass_rate"],
                shot_share=derived["shot_share"],
                turnover_rate=derived["turnover_rate"],
                archetype=derived["archetype"],
                matches=derived.get("matches"), confidence=derived.get("confidence"),
                sources=",".join(derived.get("sources") or ()),
            )
        )


def rebuild_season_profiles(session: Session, source: StatsBombSource,
                            competition_id: int, season_id: int) -> int:
    """Rebuild one competition/season's player profiles from ALL its DB matches.

    Deterministic and idempotent whatever subset was just added: the season
    accumulation is always recomputed over every match of the pair present in
    the DB, with raw events served from the on-disk cache (a match is never
    re-downloaded). This is what keeps profiles correct when ``refresh_pair``
    adds only the new matches. Returns the number of players profiled.
    """
    mids = [mid for (mid,) in session.execute(
        select(Match.id).where(Match.competition == str(competition_id),
                               Match.season == str(season_id))
    )]
    table: dict = {}
    for mid in mids:
        try:
            source.player_stats(mid, table)
        except Exception:  # noqa: BLE001 - a missing raw file skips one match
            continue
    _upsert_season_profiles(session, table, str(competition_id), str(season_id))
    rebuild_global_profiles(session, set(table.keys()))
    session.commit()
    return len(table)


def rebuild_global_profiles(session: Session, player_ids: set[str]) -> list[dict]:
    """Rebuild each player's global profile as the sum of their season rows.

    Cross-competition accumulation: a player seen in the World Cup AND La Liga
    gets one profile over all of it (previously the last ingest overwrote the
    global row). Counters are summed, matches added, sources unioned, and the
    rates/archetype/confidence re-derived by the validated ``build_profile``.
    """
    rebuilt = []
    for pid in sorted(player_ids):
        rows = session.execute(
            select(PlayerSeasonProfile).where(PlayerSeasonProfile.player_id == pid)
        ).scalars().all()
        if not rows:
            continue
        latest = max(rows, key=lambda r: (r.season or "", r.competition or ""))
        record = {
            "player_id": pid, "name": latest.name, "team": latest.team,
            "position": latest.position,
            "matches": sum(r.matches or 0 for r in rows),
            "sources": sorted({s for r in rows for s in (r.sources or "").split(",") if s}),
        }
        for f in COUNTER_FIELDS:
            record[f] = sum(getattr(r, f) or 0 for r in rows)
        rebuilt.append(build_profile(record))
    _upsert_profiles(session, rebuilt)
    return rebuilt


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

    ingested, skipped = [], []
    for raw in raw_matches:
        mid = raw["match_id"]
        try:
            ingested.append(ingest_match(session, source, mid))
        except Exception as exc:  # noqa: BLE001 - keep the pipeline going
            skipped.append((mid, str(exc)))
    session.commit()

    # Profiles: season rows (the evolution timeline) rebuilt over every match
    # of this pair in the DB, then the global profile as the exact sum of each
    # touched player's season rows.
    n_profiles = rebuild_season_profiles(session, source, competition_id, season_id)

    return {
        "competition_id": competition_id, "season_id": season_id,
        "ingested": ingested, "skipped": skipped, "profiles": n_profiles,
    }
