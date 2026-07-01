"""Phase A1 smoke test: the app boots and serves through the DB session dependency."""

from __future__ import annotations

from app.models import Match


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_matches_empty(client):
    resp = client.get("/matches")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_matches_returns_seeded_row(client, db_session):
    db_session.add(Match(id="m1", competition="Test", home_team="A", away_team="B",
                          home_goals_final=2, away_goals_final=1))
    db_session.commit()

    resp = client.get("/matches")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "m1"
    assert body[0]["home_goals_final"] == 2
