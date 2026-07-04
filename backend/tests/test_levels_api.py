"""Levels 7-12: similarity, ask, evolution, explain, benchmarks, search."""

from __future__ import annotations

import pytest

from app.models import Match, MatchEvent


def _mk(db, mid, date, home, away, goals, extra=()):
    db.add(Match(id=mid, competition="11", match_date=date, home_team=home,
                 away_team=away, status="finished",
                 home_goals_final=sum(1 for _, t in goals if t == "HOME"),
                 away_goals_final=sum(1 for _, t in goals if t == "AWAY")))
    for minute, team in goals:
        db.add(MatchEvent(match_id=mid, minute=minute, team=team, type="goal"))
    for minute, team, etype in extra:
        db.add(MatchEvent(match_id=mid, minute=minute, team=team, type=etype))


@pytest.fixture
def league(db_session):
    # m1: comeback thriller; m2: near-identical thriller; m3: quiet 0-0.
    _mk(db_session, "m1", "2016-02-01", "Alpha", "Beta",
        [(10, "AWAY"), (20, "AWAY"), (60, "HOME"), (88, "HOME")],
        [(40, "HOME", "shot"), (55, "HOME", "yellow_card"), (70, "AWAY", "red_card")])
    _mk(db_session, "m2", "2016-03-01", "Gamma", "Delta",
        [(12, "AWAY"), (22, "AWAY"), (58, "HOME"), (87, "HOME")],
        [(41, "HOME", "shot")])
    _mk(db_session, "m3", "2016-04-01", "Alpha", "Delta", [],
        [(30, "HOME", "shot"), (60, "AWAY", "corner")])
    db_session.commit()


def test_similar_ranks_the_twin_first(client, league):
    rows = client.get("/matches/m1/similar").json()
    assert rows[0]["id"] == "m2"          # the near-identical thriller
    assert rows[0]["similarity"] > rows[-1]["similarity"]
    assert rows[-1]["id"] == "m3"         # the quiet 0-0 is least similar


def test_similar_memoizes_vectors_by_events_hash(client, db_session, monkeypatch):
    """Perf: /similar memoizes each match's dynamics vector on its events digest,
    so a second request recomputes nothing and returns identical results. Matches
    carry a digest here to exercise the cache; fixtures without one bypass it."""
    import app.main as main

    main._VECTOR_CACHE.clear()
    for i, goals in enumerate([[(10, "HOME"), (80, "AWAY")],
                               [(12, "HOME"), (82, "AWAY")],
                               [(30, "AWAY")]]):
        mid = f"h{i}"
        db_session.add(Match(id=mid, competition="11", match_date=f"2016-0{i + 1}-01",
                             home_team=f"H{i}", away_team=f"A{i}", status="finished",
                             home_goals_final=1, away_goals_final=1,
                             events_hash=f"digest-{i}"))
        for minute, team in goals:
            db_session.add(MatchEvent(match_id=mid, minute=minute, team=team, type="goal"))
    db_session.commit()

    calls = {"n": 0}
    real = main.match_vector

    def counting(evs, *a, **k):
        calls["n"] += 1
        return real(evs, *a, **k)

    monkeypatch.setattr(main, "match_vector", counting)

    r1 = client.get("/matches/h0/similar").json()
    after_first = calls["n"]
    assert after_first == 3            # one vector computed per match with events
    r2 = client.get("/matches/h0/similar").json()
    assert calls["n"] == after_first   # second request: every vector served from cache
    assert r1 == r2                    # identical results whether cached or freshly computed


def test_ask_window_and_why(client, league):
    a = client.get("/matches/m1/ask", params={"q": "what happened after minute 55?"}).json()
    assert "Goal" in a["answer"] and a["intent"] == "window"
    b = client.get("/matches/m1/ask", params={"q": "why did Beta lose?"}).json()
    assert b["intent"] == "why_result" and "Beta" in b["answer"]
    c = client.get("/matches/m1/ask", params={"q": "did the referee change the game?"}).json()
    assert c["intent"] == "cards" and "red" in c["answer"]
    d = client.get("/matches/m1/ask", params={"q": "olá?"}).json()
    assert d["intent"] == "help"


def test_evolution_buckets_and_verdict(client, league):
    e = client.get("/teams/Alpha/evolution").json()
    assert e["team"] == "Alpha"
    months = {m["month"]: m for m in e["months"]}
    assert months["2016-02"]["draws"] == 1     # the 2-2
    assert months["2016-04"]["draws"] == 1     # the 0-0
    assert "goal difference" in e["verdict"]


def test_explain_cascade(client, league):
    x = client.get("/matches/m1/explain", params={"minute": 60}).json()
    assert set(x) == {"claim", "probability", "because", "evidence", "reliability"}
    assert 0 <= x["probability"] <= 1 and 0 <= x["reliability"] <= 1
    assert x["evidence"]["metrics_used"] == 8


def test_benchmarks_payload(client):
    rows = client.get("/benchmarks").json()
    assert any(r["dataset"].startswith("La Liga") and r["matches"] == 380 for r in rows)
    assert all("reproduce" in r and "source" in r for r in rows)


def test_search(client, league):
    rows = client.get("/search", params={"q": "alpha"}).json()
    assert {r["id"] for r in rows} == {"m1", "m3"}


def test_plugins_endpoint_runs_expected_chaos(client, league):
    out = client.get("/matches/m1/plugins").json()
    assert "expected_chaos" in out
    chaos = out["expected_chaos"]
    assert 0.0 <= chaos["value"] <= 1.0
    assert chaos["components"]["lead_changes"] >= 1
    assert "summary" in chaos and "description" in chaos


def test_match_detail_carries_events_hash_field(client, league):
    body = client.get("/matches/m1").json()
    assert "events_hash" in body  # provenance surfaced (None for seeded fixtures)
