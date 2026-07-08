"""Live Mode: streaming observations reproduce the batch panel exactly."""

from __future__ import annotations

from app.models import Match, MatchEvent


def _seed(db_session, mid):
    db_session.add(Match(id=mid, competition="9", season="281",
                         match_date="2023-08-19", home_team="H", away_team="A",
                         status="FT", home_goals_final=2, away_goals_final=1))
    rows = [
        (10.0, "HOME", "shot", 88.0, 40.0), (23.0, "HOME", "goal", 95.0, 50.0),
        (40.0, "AWAY", "shot", 84.0, 44.0), (55.0, "AWAY", "goal", 96.0, 52.0),
        (70.0, "HOME", "goal", 93.0, 48.0), (88.0, "HOME", "corner", 99.0, 8.0),
    ]
    for minute, team, etype, x, y in rows:
        db_session.add(MatchEvent(match_id=mid, minute=minute, team=team,
                                  type=etype, x=x, y=y))
    db_session.commit()
    return mid


def test_live_session_ingests_and_tracks_score(client, db_session):
    mid = _seed(db_session, "liveA")
    client.post(f"/live/{mid}/start")
    # Feed the first three events one at a time.
    client.post(f"/live/{mid}/observe",
                json={"minute": 10.0, "team": "HOME", "type": "shot", "x": 88.0, "y": 40.0})
    client.post(f"/live/{mid}/observe",
                json={"minute": 23.0, "team": "HOME", "type": "goal", "x": 95.0, "y": 50.0})
    state = client.post(f"/live/{mid}/observe",
                        json={"minute": 40.0, "team": "AWAY", "type": "shot", "x": 84.0, "y": 44.0}).json()
    assert state["minute"] == 40.0
    assert state["panel"]["score"] == {"home": 1, "away": 0}
    assert state["n_events"] == 3
    assert any("23' goal" in line for line in state["log"])


def test_live_observe_requires_session_and_valid_obs(client, db_session):
    mid = _seed(db_session, "liveB")
    # No session yet.
    assert client.post(f"/live/{mid}/observe",
                       json={"minute": 5, "team": "HOME", "type": "shot"}).status_code == 404
    client.post(f"/live/{mid}/start")
    assert client.post(f"/live/{mid}/observe",
                       json={"minute": 5, "team": "X", "type": "shot"}).status_code == 422


def test_live_state_is_portable_across_workers(engine):
    """The scale prerequisite: session state lives in the DB, not the process.

    One 'worker' feeds observations; a *different* session (another worker) serves
    the identical live state by rebuilding from the store."""
    from sqlalchemy.orm import sessionmaker

    from app import live
    from fie.prediction import Params

    make = sessionmaker(bind=engine)
    a = make()
    live.start(a, "portable", "H", "A", Params())
    live.observe(a, "portable", {"minute": 23.0, "team": "HOME", "type": "goal"}, Params())
    live.observe(a, "portable", {"minute": 40.0, "team": "AWAY", "type": "shot"}, Params())
    a.close()

    b = make()  # a fresh session == another worker, sharing only the database
    snap = live.state(b, "portable", Params())
    b.close()
    assert snap is not None
    assert snap["panel"]["score"] == {"home": 1, "away": 0}
    assert snap["n_events"] == 2 and snap["minute"] == 40.0


def test_replay_feed_matches_batch_panel_exactly(client, db_session):
    # The honest proof: streaming the real events one-by-one yields the same
    # panel the batch endpoint computes over the same slice.
    mid = _seed(db_session, "liveC")
    feed = client.post(f"/live/{mid}/replay_feed?upto=75").json()
    assert feed["matches_batch"] is True
    batch = client.get(f"/matches/{mid}/state?minute=75").json()
    assert feed["panel"]["score"] == batch["score"]
    assert feed["panel"]["predictions"] == batch["predictions"]
    assert feed["panel"]["regime"] == batch["regime"]
