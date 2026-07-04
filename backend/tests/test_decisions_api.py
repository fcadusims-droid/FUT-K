"""Strategic Assistant over HTTP: data-bounded, deterministic, honest."""

from __future__ import annotations

from app.models import Match, MatchEvent, ReplayStream

import json


def _seed(db_session, mid="dec1", hg=0, ag=1):
    db_session.add(Match(id=mid, competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=hg, away_goals_final=ag))
    for minute, team, etype, y in [
        (60, "HOME", "shot", 60.0), (64, "HOME", "corner", 70.0),
        (61, "AWAY", "shot", 40.0),
        # goals so the state at minute 80 is hg-ag
        *([(30, "AWAY", "goal", 50.0)] if ag else []),
    ]:
        db_session.add(MatchEvent(match_id=mid, minute=minute, team=team,
                                  type=etype, x=90.0, y=y))
    items = [{"t": 5700.0, "type": "Pass", "team": "HOME", "player": "x",
              "player_id": "1", "x": 50.0, "y": 50.0}]
    db_session.add(ReplayStream(match_id=mid, n_items=1,
                                payload=json.dumps(items), built_at="now"))
    db_session.commit()
    return mid


def test_decisions_endpoint_ranks_and_is_deterministic(client, db_session):
    mid = _seed(db_session)
    a = client.get(f"/matches/{mid}/decisions?minute=80&team=HOME&seed=1").json()
    b = client.get(f"/matches/{mid}/decisions?minute=80&team=HOME&seed=1").json()
    assert a == b
    assert a["team"] == "HOME"
    assert abs(a["horizon_minutes"] - 15.0) < 0.2   # 95 - 80, from real duration
    keys = {d["key"] for d in a["decisions"]}
    assert keys == {"keep", "attack", "defend", "control"}
    # Trailing late -> attacking should not lower the win chance vs keeping.
    by = {d["key"]: d for d in a["decisions"]}
    assert by["attack"]["win"] >= by["keep"]["win"]


def test_decisions_validates_team(client, db_session):
    mid = _seed(db_session)
    assert client.get(f"/matches/{mid}/decisions?minute=80&team=NEITHER").status_code == 422
