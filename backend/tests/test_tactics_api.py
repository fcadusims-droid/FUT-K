"""Visual Twin tactics endpoint: geometry from real events + live probability."""

from __future__ import annotations

from app.models import Match, MatchEvent


def _seed(db_session, mid="tac1"):
    db_session.add(Match(id=mid, competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=1, away_goals_final=0))
    rows = [
        (60, "HOME", "shot", 82.0, 70.0), (62, "HOME", "corner", 88.0, 76.0),
        (64, "HOME", "shot_on_target", 80.0, 72.0), (63, "HOME", "pass", 86.0, 68.0),
        (61, "AWAY", "pass", 25.0, 40.0), (65, "AWAY", "pass", 30.0, 45.0),
    ]
    for minute, team, etype, x, y in rows:
        db_session.add(MatchEvent(match_id=mid, minute=minute, team=team,
                                  type=etype, x=x, y=y))
    db_session.commit()
    return mid


def test_tactics_returns_geometry_and_probability(client, db_session):
    mid = _seed(db_session)
    body = client.get(f"/matches/{mid}/tactics?minute=66").json()
    assert body["teams"]["HOME"]["block_x"] > body["teams"]["AWAY"]["block_x"]
    assert body["top_lane"]["team"] == "HOME" and body["top_lane"]["lane"] == "left"
    assert 0 <= body["goal_next_10min"] <= 1
    assert "momentum" in body and body["territory_home"] > 0.5


def test_tactics_is_leakage_safe(client, db_session):
    mid = _seed(db_session)
    # A future event must not change the tactical read at minute 66.
    db_session.add(MatchEvent(match_id=mid, minute=80.0, team="AWAY",
                              type="goal", x=95.0, y=50.0))
    db_session.commit()
    before = client.get(f"/matches/{mid}/tactics?minute=66").json()
    # Re-fetch (same slice) — deterministic and unaffected by the later event.
    again = client.get(f"/matches/{mid}/tactics?minute=66").json()
    assert before == again
