"""Bring your own data: ingest anyone's event dataset, then calibrate on it.

FUT-K's engine is a pure function of a normalized event stream, so it does not
care where the stream came from. This module accepts the open interchange
format documented in ``docs/CUSTOM_DATA.md`` (CSV or JSON — one row per
event), validates it honestly (bad rows are reported, never silently
dropped), and writes standard matches/events rows. From there **everything**
works on your data exactly as on ours: the replay UI, the panel, Explore, and
— the point — the learning loop: ``scripts/recalibrate.py --from-db`` refits
base_rate/tau on your competition with the same promotion gate that protects
every other dataset (a refit ships only if held-out log loss does not
degrade).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fie.events import Event

from .models import Match, MatchEvent

# The engine's event vocabulary — everything the panel/prediction stack reads.
VALID_TYPES = {"goal", "shot", "shot_on_target", "corner", "foul",
               "yellow_card", "red_card"}
VALID_TEAMS = {"HOME", "AWAY"}

REQUIRED = ("match_id", "date", "home_team", "away_team", "minute", "team", "type")
OPTIONAL = ("x", "y", "player_id", "player_name")


def load_rows(path: str) -> list[dict]:
    """Rows from a .csv (DictReader) or .json (list of objects) file."""
    if path.endswith(".json"):
        rows = json.load(open(path, encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("JSON file must contain a list of event objects")
        return rows
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def validate_rows(rows: list[dict]) -> tuple[dict, list[str]]:
    """Group valid rows into matches; report every bad row with its reason.

    Returns ``(matches, errors)`` where matches is
    ``{match_id: {"meta": {...}, "events": [row, ...]}}``.
    """
    matches: dict = {}
    errors: list[str] = []
    for i, row in enumerate(rows, start=1):
        missing = [k for k in REQUIRED if not str(row.get(k) or "").strip()]
        if missing:
            errors.append(f"row {i}: missing {','.join(missing)}")
            continue
        etype = str(row["type"]).strip()
        team = str(row["team"]).strip().upper()
        if etype not in VALID_TYPES:
            errors.append(f"row {i}: unknown type '{etype}' "
                          f"(valid: {sorted(VALID_TYPES)})")
            continue
        if team not in VALID_TEAMS:
            errors.append(f"row {i}: team must be HOME or AWAY, got '{row['team']}'")
            continue
        try:
            minute = float(row["minute"])
        except (TypeError, ValueError):
            errors.append(f"row {i}: minute '{row['minute']}' is not a number")
            continue
        if not 0 <= minute <= 150 or math.isnan(minute):
            errors.append(f"row {i}: minute {minute} outside [0, 150]")
            continue

        def _coord(key):
            raw = str(row.get(key) or "").strip()
            if not raw:
                return None
            v = float(raw)
            if not 0 <= v <= 100:
                raise ValueError(f"{key} {v} outside the 0-100 pitch frame")
            return v

        try:
            x, y = _coord("x"), _coord("y")
        except ValueError as exc:
            errors.append(f"row {i}: {exc}")
            continue

        mid = str(row["match_id"]).strip()
        entry = matches.setdefault(mid, {
            "meta": {
                "match_date": str(row["date"]).strip(),
                "home_team": str(row["home_team"]).strip(),
                "away_team": str(row["away_team"]).strip(),
            },
            "events": [],
        })
        entry["events"].append({
            "minute": minute, "team": team, "type": etype, "x": x, "y": y,
            "player_id": str(row.get("player_id") or "").strip() or None,
        })
    return matches, errors


def ingest_custom(session: Session, rows: list[dict],
                  competition: str = "custom",
                  season: str | None = None,
                  replace: bool = False) -> dict:
    """Validated rows -> standard matches/events, with provenance hash.

    Idempotent: an existing match_id is skipped unless ``replace``. The final
    score is derived from the goal events themselves — one source of truth.
    """
    grouped, errors = validate_rows(rows)
    added = skipped = 0
    for mid, entry in sorted(grouped.items()):
        exists = session.get(Match, mid) is not None
        if exists and not replace:
            skipped += 1
            continue
        events = sorted(entry["events"], key=lambda e: e["minute"])
        goals_h = sum(1 for e in events if e["type"] == "goal" and e["team"] == "HOME")
        goals_a = sum(1 for e in events if e["type"] == "goal" and e["team"] == "AWAY")
        digest = hashlib.sha256(
            "|".join(f"{e['minute']:.3f},{e['team']},{e['type']},{e['player_id']}"
                     for e in events).encode()
        ).hexdigest()[:16]
        session.merge(Match(
            id=mid, competition=competition, season=season,
            match_date=entry["meta"]["match_date"],
            home_team=entry["meta"]["home_team"],
            away_team=entry["meta"]["away_team"],
            status="finished", events_hash=digest,
            home_goals_final=goals_h, away_goals_final=goals_a,
        ))
        session.execute(delete(MatchEvent).where(MatchEvent.match_id == mid))
        session.add_all(
            MatchEvent(match_id=mid, minute=e["minute"], team=e["team"],
                       type=e["type"], player_id=e["player_id"],
                       x=e["x"], y=e["y"])
            for e in events
        )
        added += 1
    session.commit()
    return {"matches_added": added, "matches_skipped": skipped,
            "rows": len(rows), "errors": errors}


def matches_from_db(session: Session, competition: str) -> list[dict]:
    """Backtest-ready match dicts from ingested rows — any competition,
    including custom ones. This is what lets the learning loop train on
    your data with zero StatsBomb involvement."""
    out = []
    match_rows = session.execute(
        select(Match).where(Match.competition == competition)
    ).scalars().all()
    for m in match_rows:
        event_rows = session.execute(
            select(MatchEvent).where(MatchEvent.match_id == m.id)
            .order_by(MatchEvent.minute)
        ).scalars().all()
        events = [
            Event(match_id=m.id, minute=r.minute, team=r.team, type=r.type,
                  player_id=r.player_id, target_id=r.target_id,
                  x=r.x, y=r.y, xg=r.xg)
            for r in event_rows
        ]
        if not events:
            continue
        out.append({
            "match_id": m.id,
            "match_date": m.match_date,
            "duration": math.ceil(max(e.minute for e in events)),
            "events": events,
        })
    return out


def example_path() -> str:
    """The shipped sample file (used by docs and tests)."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "custom_events_sample.csv",
    )
