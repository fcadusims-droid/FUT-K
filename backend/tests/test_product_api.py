"""Product-layer endpoints: humanized panel, match story, insights."""

from __future__ import annotations

import pytest

from app.models import Match, MatchEvent


@pytest.fixture
def comeback_match(db_session):
    """Away leads 2-0, home comes back to 2-2 (a 'comeback' for insights)."""
    db_session.add(Match(id="cb", competition="11", match_date="2016-01-10",
                         home_team="Alpha", away_team="Beta",
                         home_goals_final=2, away_goals_final=2, status="finished"))
    for team, minute, etype in [
        ("AWAY", 10.0, "goal"), ("AWAY", 25.0, "goal"),
        ("HOME", 60.0, "goal"), ("HOME", 88.0, "goal"),
        ("HOME", 40.0, "shot_on_target"), ("AWAY", 70.0, "shot"),
    ]:
        db_session.add(MatchEvent(match_id="cb", minute=minute, team=team, type=etype))
    db_session.commit()
    return "cb"


def test_humanized_state_no_jargon(client, comeback_match):
    resp = client.get(f"/matches/{comeback_match}/state/human", params={"minute": 30})
    assert resp.status_code == 200
    human = resp.json()["human"]
    text = " ".join([human["control"], human["situation"], human["goal_outlook"],
                     human["next_goal"]] + human["reasons"])
    # Plain language: real team names in, engine jargon out.
    assert ("Alpha" in text) or ("Beta" in text)
    for jargon in ("HOME", "AWAY", "regime", "lambda", "Poisson"):
        assert jargon not in text
    assert isinstance(human["hedged"], bool)


def test_match_story_beats(client, comeback_match):
    resp = client.get(f"/matches/{comeback_match}/story")
    assert resp.status_code == 200
    beats = resp.json()
    heads = [b["headline"] for b in beats]
    assert heads[0] == "Kick-off"
    assert heads[-1] == "Full time"
    assert sum(1 for h in heads if h.startswith("Goal")) == 4
    minutes = [b["minute"] for b in beats]
    assert minutes == sorted(minutes)  # the story flows forward
    assert "2–2" in beats[-1]["detail"]


def test_insights_comebacks(client, comeback_match):
    presets = client.get("/insights/presets").json()
    assert "comebacks" in presets
    rows = client.get("/insights/comebacks").json()
    assert any(r["id"] == "cb" for r in rows)
    assert "recovered from 2 down" in rows[0]["stat"]
    # Team filter narrows correctly.
    assert client.get("/insights/comebacks", params={"team": "Alpha"}).json()
    assert client.get("/insights/comebacks", params={"team": "Nadie"}).json() == []


def test_insights_unknown_query_404(client):
    assert client.get("/insights/nope").status_code == 404
