"""Live insights — the semantic beat layer over the live observation stream.

Each observation is turned into a live 'beat' (goal / regime shift / momentum
swing) via the same Match-Story kernel, so a raw feed (e.g. football-data.org
goals/cards) reads as live match understanding, not a bare event log.
"""

from __future__ import annotations

from app import live
from app.livefeed import sync_live
from fie.prediction import Params

# A compact football-data.org v4 match (2-1, three goals + a booking).
MATCH = {
    "id": 900, "status": "IN_PLAY", "minute": 85,
    "homeTeam": {"id": 1, "name": "Flamengo"},
    "awayTeam": {"id": 2, "name": "Palmeiras"},
    "score": {"fullTime": {"home": 2, "away": 1}},
    "goals": [
        {"minute": 20, "team": {"id": 1}, "scorer": {"id": 11}},
        {"minute": 55, "team": {"id": 2}, "scorer": {"id": 22}},
        {"minute": 80, "team": {"id": 1}, "scorer": {"id": 11}},
    ],
    "bookings": [{"minute": 78, "team": {"id": 2}, "player": {"id": 22}, "card": "RED"}],
    "substitutions": [],
}


def test_goal_beats_carry_real_names_and_running_score():
    s = live.LiveMatch("li1", "Flamengo", "Palmeiras", Params())
    s.observe({"minute": 20, "team": "HOME", "type": "goal"})
    s.observe({"minute": 55, "team": "AWAY", "type": "goal"})

    goals = [b for b in s.insights if b["headline"].startswith("Goal")]
    assert [b["headline"] for b in goals] == ["Goal — Flamengo", "Goal — Palmeiras"]
    assert "1–0" in goals[0]["detail"]      # running score at the moment of the goal
    assert "1–1" in goals[1]["detail"]


def test_a_red_card_registers_a_shift_beat():
    s = live.LiveMatch("li2", "A", "B", Params())
    for m in (10, 20, 30):
        s.observe({"minute": m, "team": "HOME", "type": "shot"})
    s.observe({"minute": 40, "team": "AWAY", "type": "red_card"})
    assert any(b["minute"] == 40 and b["headline"] == "The game changed"
               for b in s.insights)


def test_snapshot_exposes_insights():
    s = live.LiveMatch("li3", "A", "B", Params())
    assert s.snapshot()["insights"] == []          # nothing yet
    s.observe({"minute": 12, "team": "HOME", "type": "goal"})
    assert s.snapshot()["insights"][-1]["headline"] == "Goal — A"


def test_footballdata_feed_produces_live_insights():
    s = live.LiveMatch("li4", "Flamengo", "Palmeiras", Params())
    sync_live(s, MATCH)
    heads = [b["headline"] for b in s.insights]
    assert heads.count("Goal — Flamengo") == 2     # 20' and 80'
    assert "Goal — Palmeiras" in heads             # 55'


def test_endpoint_returns_insights(client, monkeypatch):
    import app.livefeed as lf

    monkeypatch.setattr(lf, "fetch_live_match", lambda fd_id, api_key=None: MATCH)
    try:
        body = client.post("/live/game_ins/footballdata?fd_id=900").json()
        goal_beats = [b for b in body["insights"] if b["headline"].startswith("Goal")]
        assert len(goal_beats) == 3                 # all three goals narrated live
    finally:
        live.stop("game_ins")
