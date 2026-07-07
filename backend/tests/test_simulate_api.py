"""Future Simulation Engine over HTTP: data-bounded horizon, determinism."""

from __future__ import annotations

import json

from app.models import Match, MatchEvent, ReplayStream


def _seed_match(db_session, mid="s1", last_second=5748.0):
    db_session.add(Match(id=mid, competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=3, away_goals_final=2))
    for minute, team, etype, y in [
        (62.0, "HOME", "shot", 72.0), (64.0, "HOME", "corner", 78.0),
        (66.0, "HOME", "shot_on_target", 70.0), (61.0, "AWAY", "shot", 20.0),
        (70.0, "HOME", "goal", 74.0),
    ]:
        db_session.add(MatchEvent(match_id=mid, minute=minute, team=team,
                                  type=etype, x=90.0, y=y))
    # Twin stream whose LAST second defines the real duration (95.8 min here).
    items = [{"t": last_second, "type": "Pass", "team": "HOME",
              "player": "x", "player_id": "1", "x": 50.0, "y": 50.0}]
    db_session.add(ReplayStream(match_id=mid, n_items=1,
                                payload=json.dumps(items), built_at="now"))
    db_session.commit()
    return mid


def test_simulate_uses_real_data_duration_not_90(client, db_session):
    mid = _seed_match(db_session, last_second=5748.0)  # 95.8 min real end
    body = client.get(f"/matches/{mid}/simulate?minute=90&n_sims=2000&seed=1").json()
    assert body["real_duration"] == 95.8
    # Horizon is the REAL remaining time (95.8 - 90 = 5.8), not 0 or a fake 90.
    assert abs(body["horizon_minutes"] - 5.8) < 0.01
    assert "twin stream" in body["duration_source"]
    assert 0 <= body["goal_prob"]["any"] <= 1


def test_simulate_is_deterministic(client, db_session):
    mid = _seed_match(db_session)
    a = client.get(f"/matches/{mid}/simulate?minute=70&n_sims=3000&seed=42").json()
    b = client.get(f"/matches/{mid}/simulate?minute=70&n_sims=3000&seed=42").json()
    assert a == b


def test_simulate_opportunity_windows_follow_real_lanes(client, db_session):
    mid = _seed_match(db_session)
    body = client.get(f"/matches/{mid}/simulate?minute=70&n_sims=8000&seed=5").json()
    home = [w for w in body["opportunity_windows"] if w["team"] == "HOME"]
    assert home
    # HOME attacked the left lane in the recent real events.
    assert home[0]["lane"] == "left"
    assert home[0]["eta_seconds"] >= 0


def test_simulate_near_full_time_has_short_horizon(client, db_session):
    mid = _seed_match(db_session, last_second=5748.0)
    body = client.get(f"/matches/{mid}/simulate?minute=95&n_sims=2000&seed=1").json()
    assert body["horizon_minutes"] < 1.0     # almost no real time left


def test_simulate_is_leakage_safe_over_http(client, db_session):
    """Erase-the-future at the API level: adding events AFTER the simulation
    minute must not change /simulate's output at that minute (73:15 discipline
    on the Future Sim path)."""
    mid = _seed_match(db_session, mid="s-leak")
    before = client.get(f"/matches/{mid}/simulate?minute=65&n_sims=500&seed=3").json()

    db_session.add(MatchEvent(match_id=mid, minute=80.0, team="AWAY", type="goal",
                              x=95.0, y=40.0))
    db_session.add(MatchEvent(match_id=mid, minute=88.0, team="HOME", type="red_card",
                              x=50.0, y=40.0))
    db_session.commit()

    after = client.get(f"/matches/{mid}/simulate?minute=65&n_sims=500&seed=3").json()
    assert before == after
