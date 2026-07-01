"""Phase A2 — ingestion pipeline (offline, deterministic, injected loaders)."""

from __future__ import annotations

from app.ingest import ingest_competition
from app.models import Match, MatchEvent, PlayerProfile
from fie.sources.statsbomb import StatsBombSource

RAW_MATCH = {
    "match_id": 555,
    "match_date": "2016-05-01",
    "home_team": {"home_team_name": "Alpha"},
    "away_team": {"away_team_name": "Beta"},
    "home_score": 2,
    "away_score": 1,
}

RAW_EVENTS = [
    {"minute": 10, "second": 0, "type": {"name": "Shot"}, "team": {"name": "Alpha"},
     "player": {"id": 1, "name": "Striker"}, "location": [110, 40],
     "shot": {"outcome": {"name": "Goal"}, "statsbomb_xg": 0.3}},
    {"minute": 30, "second": 0, "type": {"name": "Shot"}, "team": {"name": "Beta"},
     "player": {"id": 2, "name": "Forward"}, "location": [100, 40],
     "shot": {"outcome": {"name": "Goal"}, "statsbomb_xg": 0.2}},
    {"minute": 50, "second": 0, "type": {"name": "Pass"}, "team": {"name": "Alpha"},
     "player": {"id": 1, "name": "Striker"}, "location": [40, 40],
     "pass": {"end_location": [70, 40]}},
]


def _source():
    return StatsBombSource(
        11, 27,
        matches_loader=lambda: [RAW_MATCH],
        events_loader=lambda match_id: RAW_EVENTS,
    )


def test_ingest_competition_matches_and_events(db_session):
    result = ingest_competition(db_session, 11, 27, source=_source())
    assert result["ingested"] == ["555"]

    match = db_session.get(Match, "555")
    assert match.home_team == "Alpha" and match.away_goals_final == 1
    assert match.competition == "11" and match.season == "27"
    # Each goal shot maps to two normalized events (shot_on_target + goal); the
    # plain pass isn't a corner, so it contributes none to the on-field stream.
    assert len(match.events) == 4
    assert sorted(e.type for e in match.events) == [
        "goal", "goal", "shot_on_target", "shot_on_target",
    ]


def test_ingest_competition_builds_player_profiles(db_session):
    ingest_competition(db_session, 11, 27, source=_source())

    striker = db_session.get(PlayerProfile, "1")
    assert striker.goals == 1 and striker.name == "Striker"
    assert striker.archetype  # classified, not None


def test_ingest_is_idempotent(db_session):
    ingest_competition(db_session, 11, 27, source=_source())
    ingest_competition(db_session, 11, 27, source=_source())  # re-run

    n_events = db_session.query(MatchEvent).filter_by(match_id="555").count()
    assert n_events == 4  # not duplicated
    n_matches = db_session.query(Match).filter_by(id="555").count()
    assert n_matches == 1


def test_ingest_skips_failing_match_without_aborting(db_session):
    def broken_events(match_id):
        raise RuntimeError("network down")

    source = StatsBombSource(
        11, 27,
        matches_loader=lambda: [RAW_MATCH, {**RAW_MATCH, "match_id": 556}],
        events_loader=broken_events,
    )
    result = ingest_competition(db_session, 11, 27, source=source)
    assert result["ingested"] == []
    assert len(result["skipped"]) == 2
