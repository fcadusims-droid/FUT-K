"""CLI: prebuild the Digital Match Twin streams for every ingested match.

    DATABASE_URL=... python scripts/build_replay_streams.py [--competition 9]

Reads the raw event cache (shared repo-root .sb_cache), extracts the dense
on-ball stream per match (fie.sources.statsbomb.ball_stream) and stores it in
`replay_streams`. Matches without a cached raw file are skipped — the replay
UI falls back to the sparse normalized events for those.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Match, ReplayStream
from app.twin import DEFAULT_CACHE, build_stream


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--competition", default=None)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild streams that already exist")
    args = ap.parse_args()

    init_db()
    session = SessionLocal()
    try:
        stmt = select(Match).order_by(Match.id)
        if args.competition:
            stmt = stmt.where(Match.competition == args.competition)
        matches = session.execute(stmt).scalars().all()
        built = skipped = missing = 0
        for m in matches:
            if not args.rebuild and session.get(ReplayStream, m.id):
                skipped += 1
                continue
            row = build_stream(session, m, args.cache)
            if row is None:
                missing += 1
            else:
                built += 1
        print(f"matches: {len(matches)} -> streams built: {built}, "
              f"already present: {skipped}, no raw cache: {missing}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
