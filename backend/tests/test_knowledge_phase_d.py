"""Phase D over HTTP: deterministic context + behavioral indices into the store."""

from __future__ import annotations

from app.models import Match, MatchEvent, PlayerProfile


def _seed_calendar(db_session):
    # Bayern plays three matches; the third has 3 days rest and 2 in the window.
    rows = [
        ("m0", "2024-01-01", "Bayern", "Koln", 2, 0),
        ("m1", "2024-01-08", "Dortmund", "Bayern", 1, 1),
        ("m2", "2024-01-11", "Bayern", "Leipzig", 3, 2),
    ]
    for mid, dt, home, away, hg, ag in rows:
        db_session.add(Match(id=mid, competition="BL1", season="2023-24",
                             match_date=dt, home_team=home, away_team=away,
                             status="FT", home_goals_final=hg, away_goals_final=ag))
    db_session.commit()


def test_capture_context_stores_venue_rest_congestion_and_strength(client, db_session):
    _seed_calendar(db_session)
    body = client.post("/knowledge/capture-context/m2").json()
    assert body["stored"] == 2                     # one context record per team
    assert body["competition_strength"]["matches"] == 3

    recs = client.get("/knowledge/records?kind=team_context&match_id=m2").json()
    bayern = next(r for r in recs if r["context"]["team"] == "Bayern")
    assert bayern["value"]["venue"] == "home"
    assert bayern["value"]["rest_days"] == 3       # 2024-01-11 minus 2024-01-08
    assert bayern["value"]["fixture_congestion"] == 2
    assert bayern["layer"] == "observed"           # a fact, not an inference

    strength = client.get("/knowledge/records?kind=competition_strength").json()
    assert strength and strength[0]["layer"] == "derived"

    # The store stays consistent.
    assert client.get("/knowledge/audit").json()["ok"] is True


def test_capture_behavior_derives_indices_and_abstains_honestly(client, db_session):
    db_session.add(PlayerProfile(player_id="p1", name="X", team="Bayern",
                                 actions=120, pass_accuracy=0.86, turnover_rate=0.03,
                                 confidence=0.7))
    for minute, etype in [(10.0, "pass"), (20.0, "foul"), (30.0, "pass"),
                          (55.0, "pass")]:
        db_session.add(MatchEvent(match_id="m1", minute=minute, team="HOME",
                                  type=etype, player_id="p1"))
    db_session.commit()

    body = client.post("/knowledge/capture-behavior/p1").json()
    idx = body["indices"]
    assert idx["decision_stability"] is not None       # from pass_accuracy+turnovers
    assert idx["aggression_control"] is not None        # a foul is on record
    assert idx["confidence_curve"] is not None
    # Honestly abstained (data the event stream can't support):
    for name in ("leadership_index", "recovery_behavior", "tactical_discipline"):
        assert name in idx["abstained"]
    assert idx["pressure_resistance"] is None            # no dribble data on the row

    rec = client.get("/knowledge/records?kind=behavioral_profile&entity=p1").json()
    assert rec and rec[0]["layer"] == "derived"
    assert rec[0]["provenance"]["pipeline_version"] == "behavior/indices"

    assert client.post("/knowledge/capture-behavior/unknown").status_code == 404
