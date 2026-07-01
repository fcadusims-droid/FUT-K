"""Phase 1 — StatsBomb connector + SQLite (offline, deterministic).

Exercises the real-data mapping on a committed fixture shaped exactly like
StatsBomb open data, so CI needs no network. Also re-checks the no-leakage
discipline (T-20-04) on the real connector, and the SQLite round-trip.
"""

from __future__ import annotations

import json
import math
import pathlib

from fie import db as fie_db
from fie.calibration import backtest
from fie.prediction import Params
from fie.sources.statsbomb import (
    StatsBombSource,
    events_from_statsbomb,
    match_dict_from_statsbomb,
)

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "statsbomb_sample.json").read_text()
)


def _events():
    return events_from_statsbomb(
        FIXTURE["events"], "Alpha", "Beta", str(FIXTURE["match"]["match_id"])
    )


def _types(events, team=None):
    return [e.type for e in events if team is None or e.team == team]


def test_unknown_team_events_dropped():
    """Events from a team that is neither home nor away are skipped."""
    events = _events()
    # The 'Gamma' pass must not appear; 9 raw events -> 12 mapped (see below).
    assert all(e.team in ("HOME", "AWAY") for e in events)


def test_goal_emits_shot_on_target_and_goal():
    """A Shot with outcome Goal maps to a shot_on_target AND a goal."""
    home_early = [e for e in _events() if e.team == "HOME" and e.minute == 10.0]
    assert sorted(e.type for e in home_early) == ["goal", "shot_on_target"]


def test_shot_outcomes_mapped():
    """Saved -> shot_on_target; Blocked -> shot."""
    events = _events()
    saved = [e for e in events if e.team == "AWAY" and math.isclose(e.minute, 20.5)]
    assert [e.type for e in saved] == ["shot_on_target"]
    blocked = [e for e in events if e.team == "HOME" and e.minute == 25.0]
    assert [e.type for e in blocked] == ["shot"]


def test_corner_and_cards():
    """Corner pass, yellow via foul, red via foul, red via bad behaviour."""
    events = _events()
    assert any(e.type == "corner" and e.team == "HOME" and e.minute == 30.0 for e in events)
    at40 = _types([e for e in events if e.minute == 40.0])
    assert sorted(at40) == ["foul", "yellow_card"]
    at55 = _types([e for e in events if e.minute == 55.0])
    assert sorted(at55) == ["foul", "red_card"]
    at70 = _types([e for e in events if e.minute == 70.0])
    assert at70 == ["red_card"]


def test_minute_and_position_rescale():
    """minute = minute + second/60; StatsBomb 120x80 -> engine 0-100."""
    goal = next(e for e in _events() if e.type == "goal")
    assert goal.minute == 10.0
    assert math.isclose(goal.x, 110 * 100 / 120)  # 91.67
    assert math.isclose(goal.y, 40 * 100 / 80)     # 50.0
    saved = next(e for e in _events() if math.isclose(e.minute, 20.5))
    assert saved.minute == 20 + 30 / 60


def test_match_dict_shape():
    """match_dict_from_statsbomb carries teams, score and a sane duration."""
    match = match_dict_from_statsbomb(FIXTURE["match"], FIXTURE["events"])
    assert match["home_team"] == "Alpha" and match["away_team"] == "Beta"
    assert match["home_score"] == 1 and match["away_score"] == 1
    assert match["duration"] == 81  # last event at minute 80 -> 81
    assert len(match["events"]) == 12


def test_no_leakage_on_real_connector():
    """T-20-04 on real data: appending later events can't change a past prediction."""
    match = match_dict_from_statsbomb(FIXTURE["match"], FIXTURE["events"])
    at30 = dict(match, eval_minutes=[30])
    first = backtest([at30], Params())["predictions"][0]["prob"]

    # Truncate to only events up to minute 30, predict again -> must be identical.
    truncated = [e for e in match["events"] if e.minute <= 30]
    at30_trunc = dict(match, events=truncated, eval_minutes=[30])
    second = backtest([at30_trunc], Params())["predictions"][0]["prob"]
    assert first == second


def test_source_streams_mapped_events_offline():
    """StatsBombSource maps events via injected loaders — no network in CI."""
    raw_match = FIXTURE["match"]
    source = StatsBombSource(
        43, 3,
        matches_loader=lambda: [raw_match],
        events_loader=lambda match_id: FIXTURE["events"],
    )
    assert [str(m["match_id"]) for m in source.matches()] == [str(raw_match["match_id"])]
    match = source.match(raw_match["match_id"])
    assert match["home_team"] == "Alpha" and match["away_team"] == "Beta"
    streamed = list(source.stream(raw_match["match_id"]))
    assert len(streamed) == 12
    assert all(e.team in ("HOME", "AWAY") for e in streamed)


def test_sqlite_roundtrip():
    """Events and predictions persist and read back for calibration."""
    match = match_dict_from_statsbomb(FIXTURE["match"], FIXTURE["events"])
    conn = fie_db.connect(":memory:")
    fie_db.init_schema(conn)
    fie_db.insert_match(conn, match, competition="43", season="3")
    fie_db.insert_events(conn, match["match_id"], match["events"])

    result = backtest([match], Params(), window=10)
    for record, (_, happened) in zip(result["predictions"], result["pairs"]):
        fie_db.insert_prediction(conn, record, happened)
    conn.commit()

    n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert n_events == 12
    pairs = fie_db.prediction_pairs(conn)
    assert len(pairs) == len(result["pairs"])
    assert all(0.0 <= p <= 1.0 and h in (0, 1) for p, h in pairs)
