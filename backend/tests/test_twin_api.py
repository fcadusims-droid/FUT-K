"""Digital Match Twin: stream extraction, storage, endpoint, cross-check."""

from __future__ import annotations

import json

from fie.sources.statsbomb import ball_stream

from app.models import FusedMatchRecord, Match, ReplayStream

RAW = [
    {"type": {"name": "Pass"}, "minute": 0, "second": 4, "duration": 1.2,
     "location": [60.0, 40.0], "pass": {"end_location": [80.0, 50.0]},
     "team": {"name": "H"}, "player": {"id": 7, "name": "Ana"}, "period": 1},
    {"type": {"name": "Ball Receipt*"}, "minute": 0, "second": 5,
     "location": [80.0, 50.0], "team": {"name": "H"},
     "player": {"id": 8, "name": "Bia"}, "period": 1},
    {"type": {"name": "Carry"}, "minute": 0, "second": 6, "duration": 2.0,
     "location": [80.0, 50.0], "carry": {"end_location": [95.0, 44.0]},
     "team": {"name": "H"}, "player": {"id": 8, "name": "Bia"}, "period": 1},
    {"type": {"name": "Shot"}, "minute": 0, "second": 9, "duration": 0.6,
     "location": [95.0, 44.0], "shot": {"end_location": [120.0, 40.0],
                                        "outcome": {"name": "Goal"}},
     "team": {"name": "H"}, "player": {"id": 8, "name": "Bia"}, "period": 1},
    # ignored: no location / off-ball noise
    {"type": {"name": "Pressure"}, "minute": 0, "second": 7,
     "location": [70.0, 40.0], "team": {"name": "A"}, "period": 1},
    {"type": {"name": "Half Start"}, "minute": 0, "second": 0,
     "team": {"name": "H"}, "period": 1},
]


def test_ball_stream_extracts_timed_segments():
    items = ball_stream(RAW, "H")
    assert [i["type"] for i in items] == ["Pass", "Ball Receipt*", "Carry", "Shot"]
    p = items[0]
    assert p["t"] == 4.0 and p["dur"] == 1.2
    assert (p["x"], p["y"]) == (50.0, 50.0)          # 120x80 -> 0-100 frame
    assert (p["x2"], p["y2"]) == (66.67, 62.5)
    assert items[-1]["outcome"] == "Goal"
    assert items[1].get("x2") is None                # point actions: no segment
    # Deterministic
    assert ball_stream(RAW, "H") == items


def test_replay2d_endpoint_serves_stored_stream_and_404s(client, db_session):
    db_session.add(Match(id="t1", competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=1, away_goals_final=0))
    items = ball_stream(RAW, "H")
    db_session.add(ReplayStream(match_id="t1", n_items=len(items),
                                payload=json.dumps(items), built_at="now"))
    db_session.commit()

    body = client.get("/matches/t1/replay2d").json()
    assert body["n_items"] == 4 and body["items"][0]["type"] == "Pass"

    # No stream + no raw cache -> honest 404 (UI falls back to sparse events).
    db_session.add(Match(id="t2", competition="9", season="281",
                         home_team="X", away_team="Y", status="FT",
                         match_date="2023-08-20",
                         home_goals_final=0, away_goals_final=0))
    db_session.commit()
    assert client.get("/matches/t2/replay2d").status_code == 404


def test_crosscheck_resolves_fused_record(client, db_session):
    db_session.add(Match(id="t3", competition="9", season="281",
                         match_date="2024-04-14", home_team="Bayer Leverkusen",
                         away_team="SV Werder Bremen", status="FT",
                         home_goals_final=5, away_goals_final=0))
    fields = {
        "home_goals": {"value": 5, "agreed": True, "confidence": 1.0,
                       "sources": ["a", "b"], "dissent": {}},
        "corners_home": {"value": 7, "agreed": False, "confidence": 0.6,
                         "sources": ["a"], "dissent": {"b": 8}},
    }
    db_session.add(FusedMatchRecord(
        league="Bundesliga 2023/24", match_date="2024-04-14",
        home_team="bayer leverkusen", away_team="werder bremen",
        n_sources=2, sources="a,b", fields_json=json.dumps(fields),
        conflicts="corners_home", created_at="now"))
    db_session.commit()

    body = client.get("/matches/t3/crosscheck").json()
    assert body["verified"] is True and body["providers"] == 2
    assert body["fields_compared"] == 2 and body["fields_agreed"] == 1
    assert body["conflicts"] == ["corners_home"]

    # Unfused fixture: honest single-provider answer.
    db_session.add(Match(id="t4", competition="43", season="3",
                         match_date="2018-07-02", home_team="Belgium",
                         away_team="Japan", status="FT",
                         home_goals_final=3, away_goals_final=2))
    db_session.commit()
    body = client.get("/matches/t4/crosscheck").json()
    assert body["verified"] is False and body["providers"] == 1
