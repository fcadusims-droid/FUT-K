"""Recalibration cycle (product level 19): new game -> error -> update ->
recalibrate -> new version.

    DATABASE_URL=... python scripts/recalibrate.py --competition 11 --season 27

Refits base_rate/tau on the older 75% of the competition's matches, scores the
new fit AND the currently active parameters on the most recent 25%, and
promotes the new version only if it does not degrade held-out log loss. Every
attempt is recorded in `model_versions` (see GET /model/versions).
"""

from __future__ import annotations

import argparse
import os

from app.db import SessionLocal, init_db
from app.learningloop import recalibrate
from fie.sources.statsbomb import StatsBombSource

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".sb_cache",
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--competition", type=int, required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    args = ap.parse_args()

    source = StatsBombSource(args.competition, args.season, cache_dir=args.cache)
    raw = sorted(source.matches(), key=lambda m: m.get("match_date") or "")
    if args.limit:
        raw = raw[: args.limit]
    matches = []
    for rm in raw:
        try:
            matches.append(source.match(rm["match_id"]))
        except Exception as exc:  # noqa: BLE001
            print(f"  match {rm['match_id']}: skipped ({exc})")

    init_db()
    session = SessionLocal()
    try:
        v = recalibrate(session, matches, competition=str(args.competition))
        print(f"version {v.id}: base_rate={v.base_rate} tau={v.tau} "
              f"holdout LL {v.holdout_log_loss} vs active {v.baseline_log_loss} "
              f"-> {'PROMOTED' if v.promoted else 'rejected'}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
