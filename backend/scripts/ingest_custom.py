"""CLI: ingest YOUR dataset into FUT-K (bring your own data).

    DATABASE_URL=... python scripts/ingest_custom.py \
        --file my_events.csv --competition my-league

Accepts the open interchange format documented in docs/CUSTOM_DATA.md
(.csv or .json, one row per event). Bad rows are reported, never silently
dropped. After ingesting, calibrate the model on your data:

    python scripts/recalibrate.py --from-db --competition my-league
"""

from __future__ import annotations

import argparse

from app.customdata import ingest_custom, load_rows
from app.db import SessionLocal, init_db


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, help=".csv or .json event file")
    ap.add_argument("--competition", default="custom",
                    help="competition label for these matches (default: custom)")
    ap.add_argument("--season", default=None)
    ap.add_argument("--replace", action="store_true",
                    help="replace matches that already exist")
    args = ap.parse_args()

    rows = load_rows(args.file)
    init_db()
    session = SessionLocal()
    try:
        result = ingest_custom(session, rows, competition=args.competition,
                               season=args.season, replace=args.replace)
    finally:
        session.close()

    print(f"rows: {result['rows']} -> matches added: {result['matches_added']}, "
          f"skipped (already present): {result['matches_skipped']}")
    if result["errors"]:
        print(f"rejected rows ({len(result['errors'])}):")
        for e in result["errors"][:20]:
            print(f"  - {e}")
        if len(result["errors"]) > 20:
            print(f"  ... and {len(result['errors']) - 20} more")
    else:
        print("all rows valid")


if __name__ == "__main__":
    main()
