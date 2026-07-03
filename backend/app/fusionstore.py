"""Persist Data Fusion Layer output into the production DB (level 18 sibling).

The fusion pipeline (``fie.fusion``) is pure; this module is its Application
half: take resolved fixtures, fuse them, and upsert one ``FusedMatchRecord``
per fixture — idempotent by the canonical (date, home, away) key, so re-runs
update in place and never duplicate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from fie.fusion import fuse_match

from .models import FusedMatchRecord


def store_fused(session: Session, league: str, resolved: list,
                fields: dict, priors: dict | None = None) -> dict:
    """Fuse and upsert every fixture resolved across 2+ sources.

    Returns ``{"stored": n, "updated": n, "conflicts": n}``.
    """
    stored = updated = conflicts = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for fixture in resolved:
        if len(fixture["records"]) < 2:
            continue
        date, home, away = fixture["key"]
        unified = fuse_match(fixture["records"], fields, priors)
        fused_fields = {f: unified[f] for f in fields}
        row = session.execute(
            select(FusedMatchRecord).where(
                FusedMatchRecord.match_date == date,
                FusedMatchRecord.home_team == home,
                FusedMatchRecord.away_team == away,
            )
        ).scalar_one_or_none()
        if row is None:
            row = FusedMatchRecord(match_date=date, home_team=home,
                                   away_team=away, created_at=now)
            session.add(row)
            stored += 1
        else:
            updated += 1
        row.league = league
        row.n_sources = len(fixture["records"])
        row.sources = ",".join(unified["_sources"])
        row.fields_json = json.dumps(fused_fields, sort_keys=True)
        row.conflicts = ",".join(unified["_conflicts"]) or None
        conflicts += len(unified["_conflicts"])
    session.commit()
    return {"stored": stored, "updated": updated, "conflicts": conflicts}


def list_fused(session: Session, team: str | None = None,
               league: str | None = None,
               conflicts_only: bool = False, limit: int = 100) -> list[dict]:
    """Fused records, newest first, with every field's provenance unpacked."""
    stmt = select(FusedMatchRecord)
    if league:
        stmt = stmt.where(FusedMatchRecord.league == league)
    if team:
        key = team.strip().lower()
        stmt = stmt.where(
            (FusedMatchRecord.home_team.contains(key))
            | (FusedMatchRecord.away_team.contains(key))
        )
    if conflicts_only:
        stmt = stmt.where(FusedMatchRecord.conflicts.is_not(None))
    rows = session.execute(
        stmt.order_by(FusedMatchRecord.match_date.desc(),
                      FusedMatchRecord.home_team).limit(limit)
    ).scalars().all()
    return [
        {
            "league": r.league,
            "match_date": r.match_date,
            "home_team": r.home_team,
            "away_team": r.away_team,
            "n_sources": r.n_sources,
            "sources": r.sources.split(","),
            "fields": json.loads(r.fields_json),
            "conflicts": r.conflicts.split(",") if r.conflicts else [],
        }
        for r in rows
    ]
