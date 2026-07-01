"""Phase B — replay/prediction endpoints (offline, seeded SQLite)."""

from __future__ import annotations

import pytest

from app.models import Match, MatchEvent, PlayerProfile

REGIMES = {"NORMAL", "PRESSURE", "DESPERATION", "POST_GOAL", "POST_RED_CARD", "END_GAME"}


@pytest.fixture
def seeded_match(db_session):
    db_session.add(Match(id="m1", competition="43", season="3", match_date="2018-06-14",
                         home_team="Russia", away_team="Saudi Arabia",
                         home_goals_final=5, away_goals_final=0, status="finished"))
    events = [
        ("HOME", 10.0, "shot"),
        ("HOME", 12.0, "shot_on_target"),
        ("HOME", 12.0, "goal"),
        ("AWAY", 25.0, "shot"),
        ("HOME", 43.0, "shot_on_target"),
        ("HOME", 43.0, "goal"),
        ("HOME", 71.0, "corner"),
        ("HOME", 90.0, "goal"),
    ]
    for team, minute, etype in events:
        db_session.add(MatchEvent(match_id="m1", minute=minute, team=team, type=etype))
    db_session.commit()
    return "m1"


def test_match_detail(client, seeded_match):
    resp = client.get(f"/matches/{seeded_match}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["home_team"] == "Russia"
    assert body["n_events"] == 8
    assert [g["minute"] for g in body["goal_minutes"]] == [12.0, 43.0, 90.0]


def test_match_detail_404(client):
    assert client.get("/matches/nope").status_code == 404


def test_state_panel_shape_and_bounds(client, seeded_match):
    resp = client.get(f"/matches/{seeded_match}/state", params={"minute": 30})
    assert resp.status_code == 200
    panel = resp.json()

    assert panel["score"] == {"home": 1, "away": 0}  # only the minute-12 goal so far
    assert panel["regime"] in REGIMES
    assert 0.0 <= panel["confidence"] <= 1.0
    assert 0 <= panel["change_score"] <= 100
    assert abs(panel["momentum"]["home"] + panel["momentum"]["away"] - 1.0) < 1e-6
    preds = panel["predictions"]
    for key in ("goal_next_5min", "goal_next_10min", "goal_before_half"):
        assert 0.0 <= preds[key] <= 1.0
    assert abs(preds["next_goal"]["home"] + preds["next_goal"]["away"] - 1.0) < 1e-6
    assert "because" in panel["explanation"]


def test_state_is_leakage_safe_over_http(client, seeded_match, db_session):
    """T-20-04 discipline at the API level: adding future events can't change
    the panel at an earlier minute."""
    before = client.get(f"/matches/{seeded_match}/state", params={"minute": 30}).json()

    db_session.add(MatchEvent(match_id="m1", minute=60.0, team="AWAY", type="goal"))
    db_session.add(MatchEvent(match_id="m1", minute=65.0, team="AWAY", type="shot_on_target"))
    db_session.commit()

    after = client.get(f"/matches/{seeded_match}/state", params={"minute": 30}).json()
    assert before == after


def test_confidence_drops_but_not_zero_on_regime_transition(client, seeded_match):
    """Right after a goal the regime flips to POST_GOAL: confidence must drop
    (Section 10.1) but not collapse to zero — the raw 0/1 instability signal is
    smoothed before it reaches the geometric mean."""
    panel = client.get(f"/matches/{seeded_match}/state", params={"minute": 44}).json()
    assert panel["regime"] == "POST_GOAL"  # goal at minute 43
    assert 0.0 < panel["confidence"] < 0.9


def test_timeline_scrubber(client, seeded_match):
    resp = client.get(f"/matches/{seeded_match}/timeline", params={"step": 10})
    assert resp.status_code == 200
    panels = resp.json()
    assert [p["minute"] for p in panels] == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
    # score is non-decreasing through the replay
    home_goals = [p["score"]["home"] for p in panels]
    assert home_goals == sorted(home_goals)
    assert home_goals[-1] == 3


def test_player_profiles_filters(client, db_session):
    db_session.add_all([
        PlayerProfile(player_id="1", name="Finisher", team="HOME", actions=100,
                      goals=5, archetype="finisher"),
        PlayerProfile(player_id="2", name="Passer", team="AWAY", actions=300,
                      goals=0, archetype="conservative"),
        PlayerProfile(player_id="3", name="Rookie", team="HOME", actions=10,
                      goals=0, archetype="insufficient_data"),
    ])
    db_session.commit()

    all_rows = client.get("/players/profiles").json()
    assert [p["player_id"] for p in all_rows] == ["2", "1", "3"]  # by actions desc

    finishers = client.get("/players/profiles", params={"archetype": "finisher"}).json()
    assert len(finishers) == 1 and finishers[0]["name"] == "Finisher"

    active = client.get("/players/profiles", params={"min_actions": 50}).json()
    assert {p["player_id"] for p in active} == {"1", "2"}
