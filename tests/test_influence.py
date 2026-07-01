"""Section 12, Layer 4 — on/off reconstruction (offline)."""

from __future__ import annotations

from fie.players import goal_influence
from fie.sources.statsbomb import match_on_off


def _xi(team, lineup):
    return {"type": {"name": "Starting XI"}, "team": {"name": team},
            "tactics": {"lineup": [{"player": {"id": i, "name": n}} for i, n in lineup]}}


def _sub(team, off_id, off_name, on_id, on_name, minute):
    return {"type": {"name": "Substitution"}, "team": {"name": team}, "minute": minute,
            "second": 0, "player": {"id": off_id, "name": off_name},
            "substitution": {"replacement": {"id": on_id, "name": on_name}}}


def _goal(team, minute):
    return {"type": {"name": "Shot"}, "team": {"name": team}, "minute": minute, "second": 0,
            "shot": {"outcome": {"name": "Goal"}}}


EVENTS = [
    _xi("Alpha", [(1, "A"), (2, "B")]),
    _xi("Beta", [(9, "X")]),
    _goal("Alpha", 30),                       # A and B on
    _sub("Alpha", 2, "B", 3, "C", 60),        # B off, C on at 60
    _goal("Alpha", 70),                       # A and C on
    _goal("Beta", 80),                        # other team — must not count for Alpha
    {"type": {"name": "Pass"}, "team": {"name": "Alpha"}, "minute": 90, "second": 0,
     "player": {"id": 1}},                    # sets full time = 90
]


def test_match_on_off_intervals_and_goals():
    r = match_on_off(EVENTS, "Alpha")
    assert r["match_end"] == 90.0
    assert r["team_goals"] == 2  # only Alpha goals

    pp = r["per_player"]
    assert pp["1"]["on_min"] == 90.0 and pp["1"]["goals_on"] == 2   # full match, both goals
    assert pp["2"]["on_min"] == 60.0 and pp["2"]["goals_on"] == 1   # off at 60, only first goal
    assert pp["3"]["on_min"] == 30.0 and pp["3"]["goals_on"] == 1   # on at 60, only second goal


def test_on_off_influence_direction():
    """A player on for the goal-heavy spell has a positive on/off delta."""
    r = match_on_off(EVENTS, "Alpha")
    pp = r["per_player"]
    # Player C: on 30 min with 1 goal -> lambda_on high; off 60 min with 1 goal -> lower.
    on_min = pp["3"]["on_min"]
    off_min = r["match_end"] - on_min
    lam_on = pp["3"]["goals_on"] / on_min
    lam_off = (r["team_goals"] - pp["3"]["goals_on"]) / off_min
    assert goal_influence(lam_on, lam_off) > 0
