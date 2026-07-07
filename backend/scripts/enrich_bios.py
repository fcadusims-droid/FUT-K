"""CLI: enrich player profiles with real bios from Wikidata (Scout AI).

For every profiled player (>= --min-actions on-ball actions) without a bio
row, look up the *footballer* of that name on Wikidata (occupation-filtered —
a same-named non-footballer never matches) and persist birth date, height,
position and citizenship with full provenance (source, entity QID, fetch
date).

Never downloads the same fact twice: players already enriched are skipped
(unless --refresh) and every API response is cached on disk (--cache).

    DATABASE_URL=... python scripts/enrich_bios.py --min-actions 200 --limit 50
"""

from __future__ import annotations

import argparse
import os
from datetime import date

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import PlayerBio, PlayerProfile
from fie.sources.wikidata import WikidataSource

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".wd_cache",
)


def enrich(session, source: WikidataSource, min_actions: int,
           limit: int | None, refresh: bool) -> dict:
    """Enrich missing bios; returns counts. Pure orchestration (testable)."""
    have = {pid for (pid,) in session.execute(select(PlayerBio.player_id))}
    rows = session.execute(
        select(PlayerProfile)
        .where(PlayerProfile.actions >= min_actions)
        .order_by(PlayerProfile.actions.desc())
    ).scalars().all()
    todo = [r for r in rows if r.name and (refresh or r.player_id not in have)]
    if limit:
        todo = todo[:limit]

    enriched, unmatched, errors = 0, 0, 0
    for row in todo:
        try:
            bio = source.bio_for_name(row.name)
        except Exception as exc:  # noqa: BLE001 - rate limit / network: skip, keep going
            print(f"  ! {row.name}: {exc} (skipped this run)")
            errors += 1
            continue
        if bio is None:
            unmatched += 1        # unknown stays unknown — no row is written
            continue
        session.merge(PlayerBio(
            player_id=row.player_id, name=row.name,
            birth_date=bio["birth_date"], height_cm=bio["height_cm"],
            position=bio["position"], citizenship=bio["citizenship"],
            qid=bio["qid"], source=bio["source"],
            fetched_at=date.today().isoformat(),
        ))
        enriched += 1
    session.commit()
    return {"considered": len(todo), "enriched": enriched,
            "unmatched": unmatched, "errors": errors, "already_had": len(have)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-actions", type=int, default=60)
    ap.add_argument("--limit", type=int, default=None, help="max lookups this run")
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch players that already have a bio")
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="seconds between API calls (be polite)")
    args = ap.parse_args()

    init_db()
    session = SessionLocal()
    try:
        src = WikidataSource(cache_dir=args.cache, sleep_seconds=args.sleep)
        result = enrich(session, src, args.min_actions, args.limit, args.refresh)
        print(f"considered {result['considered']} players: "
              f"{result['enriched']} enriched, {result['unmatched']} without a "
              f"confident footballer match (left unknown), "
              f"{result['already_had']} already had bios (skipped)")
    finally:
        session.close()


if __name__ == "__main__":
    main()
