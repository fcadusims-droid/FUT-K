"""Digital Match Twin plumbing: build, store and serve the dense on-ball
stream that the 2D replay animates.

The stream is pure provider truth (see ``fie.sources.statsbomb.ball_stream``)
— real locations, real sub-second timestamps, nothing interpolated
server-side. Building requires the raw event cache; once built, the stream
lives in the DB and survives without the cache.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fie.sources.statsbomb import ball_stream

from .models import Match, ReplayStream

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".sb_cache",
)


def build_stream(session: Session, match: Match,
                 cache_dir: str = DEFAULT_CACHE) -> ReplayStream | None:
    """Build + persist the twin stream for one match from the raw cache.

    Returns None when the raw events file is not available (the replay then
    falls back to the sparse normalized events — honest degradation).
    """
    path = os.path.join(cache_dir, f"events_{match.id}.json")
    if not os.path.exists(path):
        return None
    raw_events = json.load(open(path, encoding="utf-8"))
    items = ball_stream(raw_events, match.home_team)
    row = ReplayStream(
        match_id=match.id,
        n_items=len(items),
        payload=json.dumps(items, ensure_ascii=False, separators=(",", ":")),
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    session.merge(row)
    session.commit()
    return row


def real_duration_minutes(session: Session, match: Match,
                          cache_dir: str = DEFAULT_CACHE) -> float | None:
    """The match's real playing time in minutes, derived from data.

    The twin stream's last recorded second is the ground truth for how long
    the match actually ran (90' + stoppage, or extra time) — never a hardcoded
    90. Returns None only when no stream and no raw cache exist.
    """
    stream = get_stream(session, match, cache_dir)
    if stream is None or not stream["items"]:
        return None
    return round(stream["items"][-1]["t"] / 60.0, 2)


def get_stream(session: Session, match: Match,
               cache_dir: str = DEFAULT_CACHE) -> dict | None:
    """Stored stream, or build-on-first-request when the cache allows it."""
    row = session.get(ReplayStream, match.id)
    if row is None:
        row = build_stream(session, match, cache_dir)
    if row is None:
        return None
    return {
        "match_id": match.id,
        "n_items": row.n_items,
        "built_at": row.built_at,
        "items": json.loads(row.payload),
    }
