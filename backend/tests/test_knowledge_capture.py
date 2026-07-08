"""Phase C over HTTP: capture the engine's inferred knowledge into the store."""

from __future__ import annotations

import json

from app.models import Match, MatchEvent, ReplayStream


def _seed_match(db_session, mid="cap1"):
    db_session.add(Match(id=mid, competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=3, away_goals_final=2))
    for minute, team, etype, y in [
        (62.0, "HOME", "shot", 72.0), (64.0, "HOME", "corner", 78.0),
        (66.0, "HOME", "shot_on_target", 70.0), (70.0, "HOME", "goal", 74.0),
    ]:
        db_session.add(MatchEvent(match_id=mid, minute=minute, team=team,
                                  type=etype, x=90.0, y=y))
    db_session.add(ReplayStream(match_id=mid, n_items=1, built_at="now",
                                payload=json.dumps([{"t": 5748.0, "type": "Pass",
                                                     "team": "HOME", "player": "x",
                                                     "player_id": "1", "x": 50.0,
                                                     "y": 50.0}])))
    db_session.commit()
    return mid


def test_capture_persists_predictions_and_simulation(client, db_session):
    mid = _seed_match(db_session)
    body = client.post(f"/knowledge/capture/{mid}?minute=70&n_sims=500&seed=1").json()
    assert body["predictions"]["stored"] == 4        # four predicted targets
    assert body["simulation"]["stored"] >= 1

    # Predictions are PROBABILISTIC, the simulation SIMULATED — separated, and
    # each pinned to the match.
    probs = client.get(f"/knowledge/records?layer=probabilistic&match_id={mid}").json()
    assert probs and all(r["kind"].startswith("pred_") for r in probs)
    sims = client.get(f"/knowledge/records?layer=simulated&match_id={mid}").json()
    assert sims and all(r["kind"].startswith("sim_") for r in sims)
    # Nothing lifted here masquerades as observed fact.
    obs = client.get(f"/knowledge/records?layer=observed&match_id={mid}").json()
    assert obs == []

    # The store stays consistent under the continuous audit.
    assert client.get("/knowledge/audit").json()["ok"] is True


def test_capture_is_idempotent(client, db_session):
    mid = _seed_match(db_session, mid="cap2")
    first = client.post(f"/knowledge/capture/{mid}?minute=70&n_sims=500&seed=1").json()
    again = client.post(f"/knowledge/capture/{mid}?minute=70&n_sims=500&seed=1").json()
    # Same minute + seed => same content-addressed ids => updates, not duplicates.
    assert first["predictions"]["stored"] == 4
    assert again["predictions"]["stored"] == 0 and again["predictions"]["updated"] == 4


def test_capture_predictions_only(client, db_session):
    mid = _seed_match(db_session, mid="cap3")
    body = client.post(f"/knowledge/capture/{mid}?minute=70&simulate=false").json()
    assert body["predictions"]["stored"] == 4
    assert "simulation" not in body
