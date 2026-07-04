"""Phase 2 — the football-data.org live feed (offline, monkeypatched fetch)."""

from __future__ import annotations

from app import live
from app.livefeed import sync_live
from fie.prediction import Params

# A compact football-data.org v4 match (the shape the connector maps): 2-1,
# three goals and a booking, live at minute 85.
MATCH = {
    "id": 900, "status": "IN_PLAY", "minute": 85,
    "homeTeam": {"id": 1, "name": "Home FC"},
    "awayTeam": {"id": 2, "name": "Away FC"},
    "score": {"fullTime": {"home": 2, "away": 1}},
    "goals": [
        {"minute": 20, "team": {"id": 1}, "scorer": {"id": 11}},
        {"minute": 55, "team": {"id": 2}, "scorer": {"id": 22}},
        {"minute": 80, "team": {"id": 1}, "scorer": {"id": 11}},
    ],
    "bookings": [{"minute": 40, "team": {"id": 2}, "player": {"id": 22}, "card": "YELLOW"}],
    "substitutions": [],
}


def test_sync_live_feeds_new_events_then_is_idempotent():
    session = live.LiveMatch("t1", "Home FC", "Away FC", Params())

    fed = sync_live(session, MATCH)
    assert fed == 4                                   # 3 goals + 1 card
    assert len(session.events) == 4
    assert session.minute == 85.0                     # clock advanced to provider minute
    assert session.snapshot()["panel"]["score"] == {"home": 2, "away": 1}

    # Polling the same match again feeds nothing — safe on an interval.
    assert sync_live(session, MATCH) == 0
    assert len(session.events) == 4


def test_sync_live_picks_up_a_later_goal():
    session = live.LiveMatch("t2", "Home FC", "Away FC", Params())
    sync_live(session, MATCH)
    later = {**MATCH, "minute": 90,
             "score": {"fullTime": {"home": 3, "away": 1}},
             "goals": MATCH["goals"] + [{"minute": 88, "team": {"id": 1}, "scorer": {"id": 11}}]}
    assert sync_live(session, later) == 1             # only the new goal
    assert session.snapshot()["panel"]["score"] == {"home": 3, "away": 1}


def test_endpoint_feeds_session_and_is_idempotent(client, monkeypatch):
    import app.livefeed as lf

    monkeypatch.setattr(lf, "fetch_live_match", lambda fd_id, api_key=None: MATCH)
    try:
        body = client.post("/live/game1/footballdata?fd_id=900").json()
        assert body["new_events"] == 4
        assert body["panel"]["score"] == {"home": 2, "away": 1}
        assert body["source"] == "football-data.org" and body["fd_status"] == "IN_PLAY"

        assert client.post("/live/game1/footballdata?fd_id=900").json()["new_events"] == 0
    finally:
        live.stop("game1")


def test_endpoint_404_when_match_missing(client, monkeypatch):
    import app.livefeed as lf

    monkeypatch.setattr(lf, "fetch_live_match", lambda fd_id, api_key=None: {})
    assert client.post("/live/g2/footballdata?fd_id=1").status_code == 404


def test_endpoint_502_on_provider_error(client, monkeypatch):
    import app.livefeed as lf

    def boom(fd_id, api_key=None):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(lf, "fetch_live_match", boom)
    assert client.post("/live/g3/footballdata?fd_id=1").status_code == 502
