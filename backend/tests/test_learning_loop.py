"""Levels 18-19: incremental refresh + quality audit + recalibration gate."""

from __future__ import annotations

import pytest

from app.learningloop import get_active_params, quality_issues, recalibrate, refresh_pair
from app.models import IngestionRun, Match, MatchEvent
from fie.events import Event


class FakeSource:
    """Injectable source: two matches, StatsBomb-shaped surface."""

    competition_id = 11
    season_id = 27

    def __init__(self):
        self._matches = {
            "n1": {"match_id": "n1", "match_date": "2016-05-01", "home_team": "Alpha",
                   "away_team": "Beta", "home_score": 1, "away_score": 0, "duration": 91,
                   "events": [Event("n1", 40.0, "HOME", "goal"),
                              Event("n1", 20.0, "HOME", "shot")]},
            "old1": {"match_id": "old1", "match_date": "2016-04-01", "home_team": "Alpha",
                     "away_team": "Gamma", "home_score": 0, "away_score": 0, "duration": 90,
                     "events": [Event("old1", 30.0, "AWAY", "shot")]},
        }

    def matches(self):
        return [{"match_id": k, "match_date": v["match_date"]}
                for k, v in self._matches.items()]

    def match(self, match_id):
        return self._matches[str(match_id)]


def test_refresh_is_incremental_and_audited(db_session):
    # 'old1' is already in the DB — only 'n1' must be ingested.
    db_session.add(Match(id="old1", competition="11", season="27",
                         home_team="Alpha", away_team="Gamma", status="finished",
                         home_goals_final=0, away_goals_final=0))
    db_session.commit()

    run = refresh_pair(db_session, 11, 27, source=FakeSource())
    assert run.matches_added == 1 and run.matches_skipped == 1
    assert run.matches_failed == 0
    assert run.quality_ok is True
    assert db_session.get(Match, "n1") is not None
    assert db_session.query(IngestionRun).count() == 1

    # Second run: nothing new, still audited.
    run2 = refresh_pair(db_session, 11, 27, source=FakeSource())
    assert run2.matches_added == 0 and run2.matches_skipped == 2


def test_quality_flags_score_mismatch(db_session):
    db_session.add(Match(id="bad", competition="11", season="27",
                         home_team="A", away_team="B", status="finished",
                         home_goals_final=2, away_goals_final=0))
    db_session.add(MatchEvent(match_id="bad", minute=40.0, team="HOME", type="goal"))
    db_session.commit()
    issues = quality_issues(db_session, "bad")
    assert issues and "goal events 1-0 != final 2-0" in issues[0]


def _synthetic_matches(n=16, goal_every=10.0):
    """High-scoring synthetic matches: a goal every `goal_every` minutes."""
    out = []
    for i in range(n):
        events = [Event(f"s{i}", m, "HOME" if int(m) % 2 else "AWAY", "goal")
                  for m in [goal_every * k for k in range(1, int(90 / goal_every))]]
        out.append({"match_id": f"s{i}", "match_date": f"2016-01-{i+1:02d}",
                    "duration": 90, "events": events})
    return out


def test_recalibrate_promotes_and_serves_params(db_session):
    # Default params (base_rate 0.015 ~ 2.7 goals/match) badly under-predict a
    # world with ~8 goals/match; the refit must win the holdout and be promoted.
    matches = _synthetic_matches()
    v = recalibrate(db_session, matches, competition="test")
    assert v.promoted is True
    assert v.base_rate > 0.015
    assert v.holdout_log_loss <= v.baseline_log_loss

    active = get_active_params(db_session)
    assert active.base_rate == v.base_rate and active.tau == v.tau

    # A second identical run cannot beat the (now identical) active params in a
    # way that degrades — the gate keeps the better-or-equal version only.
    v2 = recalibrate(db_session, matches, competition="test")
    assert v2.holdout_log_loss <= v2.baseline_log_loss or v2.promoted is False


def test_recalibrate_needs_sample(db_session):
    with pytest.raises(ValueError):
        recalibrate(db_session, _synthetic_matches(n=4))


def test_model_versions_endpoint(client, db_session):
    recalibrate(db_session, _synthetic_matches(), competition="test")
    rows = client.get("/model/versions").json()
    assert rows and rows[0]["promoted"] is True
    assert rows[0]["competition"] == "test"
