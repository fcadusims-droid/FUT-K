"""Phase D — deterministic contextual data derived from the calendar."""

from __future__ import annotations

from fie.context import (
    competition_strength,
    fixture_congestion,
    match_context,
    rest_days,
)

DATES = ["2024-01-01", "2024-01-08", "2024-01-11", "2024-01-20"]


def test_rest_days_counts_gap_to_previous_match():
    assert rest_days(DATES, "2024-01-11") == 3       # since 2024-01-08
    assert rest_days(DATES, "2024-01-08") == 7       # since 2024-01-01
    # First known match: nothing to measure from -> abstain.
    assert rest_days(DATES, "2024-01-01") is None
    assert rest_days(DATES, "not-a-date") is None


def test_fixture_congestion_counts_recent_matches():
    # In the 14 days before 2024-01-20: 2024-01-08 and 2024-01-11 (not the 1st).
    assert fixture_congestion(DATES, "2024-01-20", window_days=14) == 2
    assert fixture_congestion(DATES, "2024-01-08", window_days=14) == 1
    assert fixture_congestion(DATES, "2024-01-01", window_days=14) == 0


def test_competition_strength_is_mean_goals_per_match():
    s = competition_strength([2, 3, 1, 4, None])
    assert s == {"goals_per_match": 2.5, "matches": 4}   # None ignored
    assert competition_strength([]) is None


def test_match_context_bundles_venue_rest_congestion():
    ctx = match_context("Bayern", True, DATES, "2024-01-11")
    assert ctx["venue"] == "home"
    assert ctx["rest_days"] == 3
    assert ctx["fixture_congestion"] == 2
    away = match_context("Bayern", False, DATES, "2024-01-11")
    assert away["venue"] == "away"


def test_context_helpers_are_deterministic():
    a = match_context("X", True, DATES, "2024-01-20")
    b = match_context("X", True, list(DATES), "2024-01-20")
    assert a == b
