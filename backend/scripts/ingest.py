"""CLI: ingest one or more StatsBomb competition/season pairs into the
production DB (Phase A2). Reuses the shared ``.sb_cache`` at the repo root
populated by the earlier validation/analysis phases.

    DATABASE_URL=postgresql+psycopg://fie_app:pw@localhost/fie_dev \
        python scripts/ingest.py --pairs 43/3,11/27 --limit 40
"""

from __future__ import annotations

import argparse
import os

from app.db import SessionLocal, init_db
from app.ingest import ingest_competition

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".sb_cache",
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pairs", required=True,
        help="comma-separated competition/season id pairs, e.g. 43/3,11/27",
    )
    ap.add_argument("--limit", type=int, default=None, help="max matches per competition")
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    args = ap.parse_args()

    init_db()
    session = SessionLocal()
    try:
        for pair in args.pairs.split(","):
            comp, season = (int(x) for x in pair.strip().split("/"))
            result = ingest_competition(
                session, comp, season, cache_dir=args.cache, limit=args.limit
            )
            print(
                f"{comp}/{season}: {len(result['ingested'])} matches ingested, "
                f"{result['profiles']} player profiles, {len(result['skipped'])} skipped"
            )
            for mid, err in result["skipped"]:
                print(f"  skipped {mid}: {err}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
