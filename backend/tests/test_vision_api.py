"""Vision Engine over HTTP: estimated state + self-evaluation."""

from __future__ import annotations

import json

from app.models import Match, ReplayStream


def _seed(db_session, mid="vis1"):
    db_session.add(Match(id=mid, competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=0, away_goals_final=0))
    # p1 observed across several seconds; p2 seen once early (goes stale).
    items = [
        {"t": 600.0, "x": 40.0, "y": 50.0, "player_id": "p1", "player": "Ana"},
        {"t": 601.5, "x": 46.0, "y": 52.0, "player_id": "p1", "player": "Ana"},
        {"t": 603.0, "x": 52.0, "y": 55.0, "player_id": "p1", "player": "Ana"},
        {"t": 604.5, "x": 58.0, "y": 57.0, "player_id": "p1", "player": "Ana"},
        {"t": 601.0, "x": 20.0, "y": 20.0, "player_id": "p2", "player": "Bia"},
    ]
    db_session.add(ReplayStream(match_id=mid, n_items=len(items),
                                payload=json.dumps(items), built_at="now"))
    db_session.commit()
    return mid


def test_vision_returns_estimated_state_with_confidence(client, db_session):
    mid = _seed(db_session)
    # At 603s exactly, p1 was just observed -> confidence 1; p2 stale ~2s.
    body = client.get(f"/matches/{mid}/vision?minute={603/60:.4f}").json()
    ents = body["entities"]
    assert ents["p1"]["observed"] and ents["p1"]["confidence"] == 1.0
    assert ents["p2"]["confidence"] < 1.0 and ents["p2"]["x"] == 20.0  # held


def test_vision_self_evaluation_reports_honest_metrics(client, db_session):
    mid = _seed(db_session)
    body = client.get(f"/matches/{mid}/vision?minute=10.05&evaluate=true").json()
    ev = body["self_evaluation"]
    # p1 has 3 observations -> at least one prediction scored, with a baseline.
    assert ev["n"] >= 1
    assert "static_baseline_mean" in ev and "beats_static_by" in ev


def test_vision_404_without_stream(client, db_session):
    db_session.add(Match(id="nostream", competition="9", season="281",
                         home_team="X", away_team="Y", status="FT",
                         match_date="2023-08-20",
                         home_goals_final=0, away_goals_final=0))
    db_session.commit()
    assert client.get("/matches/nostream/vision?minute=45").status_code == 404
