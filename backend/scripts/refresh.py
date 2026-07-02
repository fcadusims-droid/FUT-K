"""Daily data refresh (product level 18): incremental, audited ingestion.

    DATABASE_URL=... python scripts/refresh.py --pairs 11/27,43/3

Only matches not yet in the DB are ingested; every run writes an audit row to
`ingestion_runs` with counts and data-quality notes. Schedule via cron:

    0 6 * * *  cd /srv/futk/backend && python scripts/refresh.py --pairs 11/27
"""

from __future__ import annotations

import argparse
import os

from app.db import SessionLocal, init_db
from app.learningloop import refresh_pair

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".sb_cache",
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", required=True, help="e.g. 43/3,11/27")
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    args = ap.parse_args()

    init_db()
    session = SessionLocal()
    try:
        for pair in args.pairs.split(","):
            comp, season = (int(x) for x in pair.strip().split("/"))
            run = refresh_pair(session, comp, season, cache_dir=args.cache)
            print(f"{pair}: +{run.matches_added} new, {run.matches_skipped} known, "
                  f"{run.matches_failed} failed, quality_ok={run.quality_ok}")
            if run.quality_notes:
                print(f"  notes: {run.quality_notes}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
