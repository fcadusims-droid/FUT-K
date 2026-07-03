"""CLI: run the Data Fusion Layer and persist fused records into the DB.

    DATABASE_URL=postgresql+psycopg://fie_app:pw@localhost/fie_dev \
        python scripts/ingest_fused.py --leagues bundesliga-2324,premier-league-2324

Downloads are cached in the shared repo-root ``.sb_cache``; every run after
the first is offline. Idempotent: fixtures upsert by their canonical
(date, home, away) key.
"""

from __future__ import annotations

import argparse
import os

from app.db import SessionLocal, init_db
from app.fusionstore import store_fused

from fie.fusion import resolve_matches
from fie.sources.providers import FIELDS, FUSION_LEAGUES, PRIORS, load_league_sources

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".sb_cache",
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leagues", default=",".join(FUSION_LEAGUES),
                    help=f"comma-separated presets from {sorted(FUSION_LEAGUES)}")
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    args = ap.parse_args()

    init_db()
    session = SessionLocal()
    try:
        for key in (k.strip() for k in args.leagues.split(",") if k.strip()):
            label = FUSION_LEAGUES[key]["label"]
            print(f"{label}: loading sources ...")
            resolved = resolve_matches(load_league_sources(key, args.cache))
            result = store_fused(session, label, resolved, FIELDS, PRIORS)
            print(f"  {result}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
