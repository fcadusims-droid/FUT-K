"""What If? counterfactuals: pure re-reads, exact score edits, honest 404s."""

from __future__ import annotations

import pytest

from app.models import Match, MatchEvent


@pytest.fixture
def seeded(db_session):
    db_session.add(Match(id="w1", competition="43", season="3",
                         home_team="H", away_team="A", status="FT",
                         home_goals_final=2, away_goals_final=1))
    rows = [
        (10.0, "HOME", "shot_on_target"),
        (23.0, "HOME", "goal"),
        (40.0, "AWAY", "yellow_card"),
        (55.0, "AWAY", "goal"),
        (70.0, "HOME", "goal"),
        (88.0, "HOME", "corner"),
    ]
    for minute, team, etype in rows:
        db_session.add(MatchEvent(match_id="w1", minute=minute, team=team, type=etype))
    db_session.commit()
    return "w1"


def test_whatif_removing_a_goal_changes_the_score_downstream(client, seeded):
    r = client.get("/matches/w1/whatif?minute=55&type=goal&team=AWAY")
    assert r.status_code == 200
    body = r.json()
    assert body["removed"] == {"minute": 55.0, "type": "goal", "team": "AWAY"}
    assert body["from_minute"] == 55
    # Baseline ends 2-1; without AWAY's goal the engine reads 2-0.
    assert body["baseline"]["score"][-1] == [2, 1]
    assert body["counterfactual"]["score"][-1] == [2, 0]
    # Aligned series over the same minutes; a note that states what this is.
    n = len(body["minutes"])
    assert all(len(body[k]["goal_next_10min"]) == n
               for k in ("baseline", "counterfactual"))
    assert "re-reading" in body["note"]
    assert "reading" in body and body["reading"]

    # Deterministic: an identical request returns identical numbers.
    assert client.get("/matches/w1/whatif?minute=55&type=goal&team=AWAY").json() == body


def test_whatif_validation_and_404(client, seeded):
    # Unremovable type and bad team are rejected up front.
    assert client.get("/matches/w1/whatif?minute=10&type=shot&team=HOME").status_code == 422
    assert client.get("/matches/w1/whatif?minute=23&type=goal&team=BOTH").status_code == 422
    # Pointing at nothing is a 404, not a silent no-op.
    assert client.get("/matches/w1/whatif?minute=5&type=goal&team=HOME").status_code == 404
    assert client.get("/matches/nope/whatif?minute=23&type=goal&team=HOME").status_code == 404
