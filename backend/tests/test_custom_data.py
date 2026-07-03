"""Bring-your-own-data: honest validation, ingestion, and calibration."""

from __future__ import annotations

from app.customdata import (
    example_path,
    ingest_custom,
    load_rows,
    matches_from_db,
    validate_rows,
)
from app.learningloop import recalibrate


def test_validate_rows_reports_every_bad_row_with_reason():
    rows = [
        {"match_id": "m1", "date": "2025-01-01", "home_team": "A", "away_team": "B",
         "minute": "10", "team": "HOME", "type": "goal"},
        {"match_id": "m1", "date": "2025-01-01", "home_team": "A", "away_team": "B",
         "minute": "12", "team": "BOTH", "type": "goal"},           # bad team
        {"match_id": "m1", "date": "2025-01-01", "home_team": "A", "away_team": "B",
         "minute": "12", "team": "HOME", "type": "throw_in"},        # bad type
        {"match_id": "m1", "date": "2025-01-01", "home_team": "A", "away_team": "B",
         "minute": "999", "team": "HOME", "type": "shot"},           # bad minute
        {"match_id": "m1", "date": "2025-01-01", "home_team": "A", "away_team": "B",
         "minute": "20", "team": "AWAY", "type": "shot", "x": "140"},  # bad coord
        {"match_id": "", "date": "2025-01-01", "home_team": "A", "away_team": "B",
         "minute": "20", "team": "AWAY", "type": "shot"},            # missing id
    ]
    grouped, errors = validate_rows(rows)
    assert len(grouped["m1"]["events"]) == 1          # only the valid row
    assert len(errors) == 5
    assert any("BOTH" in e for e in errors)
    assert any("throw_in" in e for e in errors)
    assert any("999" in e for e in errors)
    assert any("140" in e for e in errors)
    assert any("missing match_id" in e for e in errors)


def test_ingest_sample_file_and_replay_it_over_http(client, db_session):
    rows = load_rows(example_path())
    result = ingest_custom(db_session, rows, competition="my-league")
    assert result["matches_added"] == 10 and result["errors"] == []

    # Idempotent: second run skips everything.
    again = ingest_custom(db_session, rows, competition="my-league")
    assert again == {**again, "matches_added": 0, "matches_skipped": 10}

    # The custom matches are first-class citizens of the API.
    matches = client.get("/matches?competition=my-league").json()
    assert len(matches) == 10
    mid = matches[0]["id"]
    detail = client.get(f"/matches/{mid}").json()
    # Final score was derived from the goal events themselves.
    goals = [e for e in client.get(f"/matches/{mid}/events").json()
             if e["type"] == "goal"]
    home_goals = sum(1 for g in goals if g["team"] == "HOME")
    assert detail["home_goals_final"] == home_goals
    # The intelligent panel replays custom data like any other match.
    panel = client.get(f"/matches/{mid}/state?minute=45").json()
    assert 0 <= panel["predictions"]["goal_next_10min"] <= 1


def test_recalibrate_from_db_runs_the_gate_on_custom_data(db_session):
    ingest_custom(db_session, load_rows(example_path()), competition="my-league")
    matches = matches_from_db(db_session, "my-league")
    assert len(matches) == 10 and all(m["events"] for m in matches)

    version = recalibrate(db_session, matches, competition="my-league")
    # The learning loop ran and recorded an auditable verdict either way.
    assert version.competition == "my-league"
    assert version.holdout_log_loss > 0
    assert version.promoted in (True, False)
    assert "held-out" in version.note
