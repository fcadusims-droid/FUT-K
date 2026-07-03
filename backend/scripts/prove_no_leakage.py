"""The 73:15 test — prove the engine never sees the future, on YOUR data.

    DATABASE_URL=... python scripts/prove_no_leakage.py

The question that defines whether the model is honest: *stop a match at
exactly 73:15, erase everything that happened after that instant — does
FUT-K still produce exactly the same prediction it produced originally?*

For every ingested match and a battery of cutoffs (73.25 = 73:15 included),
this script computes the full panel twice — once from the complete event
stream, once from a stream with the future ERASED — and compares the JSON
payloads **byte for byte**. Any difference is information leakage and is
reported as a failure.

This is the same property the test suite enforces on every push (T-20-04 at
the engine level, `backend/tests/test_replay_api.py -k leak` at the HTTP
level); this script re-proves it at full scale on whatever data you have
ingested — including your own datasets (docs/CUSTOM_DATA.md).
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.learningloop import get_active_params
from app.models import Match, MatchEvent
from app.panel import _row_to_event, panel_state

CUTOFFS = [5.0, 15.0, 30.0, 44.9, 45.0, 60.0, 73.25, 85.0, 90.0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--every", type=int, default=1,
                    help="sample every Nth match (default: all)")
    args = ap.parse_args()

    init_db()
    session = SessionLocal()
    params = get_active_params(session)
    matches = session.execute(select(Match).order_by(Match.id)).scalars().all()
    sample = matches[:: args.every]

    total = identical = 0
    failures = []
    for m in sample:
        rows = session.execute(
            select(MatchEvent).where(MatchEvent.match_id == m.id)
            .order_by(MatchEvent.minute, MatchEvent.id)
        ).scalars().all()
        events = [_row_to_event(r) for r in rows]
        if not events:
            continue
        for t in CUTOFFS:
            full = panel_state(events, t, match_id=m.id, params=params)
            erased = [e for e in events if e.minute <= t]  # future DELETED
            trunc = panel_state(erased, t, match_id=m.id, params=params)
            total += 1
            if json.dumps(full, sort_keys=True) == json.dumps(trunc, sort_keys=True):
                identical += 1
            else:
                failures.append((m.id, t))
    session.close()

    print(f"matches: {len(sample)} · cutoffs per match: {len(CUTOFFS)} "
          f"(73.25 = the 73:15 question)")
    print(f"comparisons: {total} · byte-identical: {identical}/{total}")
    if failures:
        print(f"LEAKAGE DETECTED in {len(failures)} cases: {failures[:10]}")
        raise SystemExit(1)
    print("NO LEAKAGE: erasing the future never changes a prediction.")


if __name__ == "__main__":
    main()
