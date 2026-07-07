"""Section 12 — player DNA profiling (offline, deterministic)."""

from __future__ import annotations

import json
import math
import pathlib

import pytest

from fie import db as fie_db
from fie.profiling import (
    MIN_ACTIONS,
    build_profile,
    profile_avatar,
    profile_confidence,
    real_archetype,
)
from fie.sources.statsbomb import accumulate_player_stats

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "statsbomb_players.json").read_text()
)


def _table():
    return accumulate_player_stats(FIXTURE["events"], FIXTURE["home_team"], FIXTURE["away_team"])


def test_unknown_team_dropped():
    """Players from a team that is neither home nor away are skipped."""
    table = _table()
    assert set(table) == {"100", "200"}  # 'Gamma' player 300 excluded


def test_striker_counters():
    """Counters are accumulated correctly from the rich StatsBomb events."""
    rec = _table()["100"]
    assert rec["shots"] == 2 and rec["goals"] == 1
    assert rec["passes"] == 2 and rec["passes_completed"] == 1  # one Incomplete
    assert rec["progressive"] == 1                              # 40->70 forward
    assert rec["dribbles"] == 1 and rec["dribbles_completed"] == 1
    assert rec["turnovers"] == 1                                # Dispossessed
    assert rec["actions"] == 5                                  # 2 shots + 2 passes + 1 dribble


def test_playmaker_counters():
    """Key passes and assists are read from shot_assist / goal_assist."""
    rec = _table()["200"]
    assert rec["passes"] == 3 and rec["passes_completed"] == 3
    assert rec["key_passes"] == 1 and rec["assists"] == 1
    assert rec["actions"] == 4  # 3 passes + 1 carry


def test_build_profile_rates():
    """Derived shares/rates match the counters."""
    profile = build_profile(_table()["100"])
    assert profile["pass_accuracy"] == 0.5
    assert math.isclose(profile["shot_share"], 2 / 5)
    assert math.isclose(profile["turnover_rate"], 1 / 5)
    assert profile["progressive_pass_share"] == 1.0
    assert profile["archetype"] == "insufficient_data"  # only 5 actions


ARCH_BASE = {
    "actions": 100, "shots": 0, "shot_share": 0.0, "key_pass_rate": 0.0, "assists": 0,
    "turnover_rate": 0.0, "dribbles": 0, "dribble_success": 1.0, "pass_accuracy": 0.7,
}


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"shot_share": 0.06, "shots": 10}, "finisher"),
        ({"key_pass_rate": 0.05}, "creator"),
        ({"assists": 3}, "creator"),
        ({"turnover_rate": 0.05, "dribbles": 15, "dribble_success": 0.4}, "impulsive"),
        ({"pass_accuracy": 0.9, "shot_share": 0.01}, "conservative"),
        ({}, "balanced"),
        ({"actions": 10}, "insufficient_data"),
    ],
)
def test_real_archetype_rules(overrides, expected):
    """Each archetype is reachable and thresholds behave as documented."""
    assert real_archetype({**ARCH_BASE, **overrides}) == expected


def test_profile_avatar_normalized():
    """The avatar vector is normalized into [0, 1] on every dimension."""
    profile = build_profile(_table()["200"])
    for value in profile_avatar(profile).values():
        assert 0.0 <= value <= 1.0


def test_min_actions_constant_used():
    """A profile just below MIN_ACTIONS is insufficient_data, at/above is classified."""
    below = {**ARCH_BASE, "actions": MIN_ACTIONS - 1, "shot_share": 0.06, "shots": 10}
    at = {**ARCH_BASE, "actions": MIN_ACTIONS, "shot_share": 0.06, "shots": 10}
    assert real_archetype(below) == "insufficient_data"
    assert real_archetype(at) == "finisher"


def test_profile_confidence_curve():
    """Confidence saturates in [0, 1): zero with no evidence, 0.5 exactly at the
    archetype threshold, strictly increasing, never certain."""
    assert profile_confidence(0) == 0.0
    assert profile_confidence(MIN_ACTIONS) == 0.5  # anchored to the archetype gate
    assert profile_confidence(3 * MIN_ACTIONS) == 0.75
    curve = [profile_confidence(a) for a in (0, 10, 60, 200, 1000)]
    assert curve == sorted(curve) and len(set(curve)) == len(curve)  # strictly up
    assert all(0.0 <= c < 1.0 for c in curve)
    assert profile_confidence(-5) == 0.0  # defensive: never negative


def test_provenance_tracked_across_matches():
    """Match count and sources accumulate honestly across calls; a profile
    reports how much real evidence — and from which datasets — backs it."""
    table = {}
    accumulate_player_stats(FIXTURE["events"], FIXTURE["home_team"],
                            FIXTURE["away_team"], table, source="statsbomb")
    accumulate_player_stats(FIXTURE["events"], FIXTURE["home_team"],
                            FIXTURE["away_team"], table, source="statsbomb")
    # Same source twice, two matches: matches counts to 2, source deduplicated.
    assert table["100"]["matches"] == 2
    assert table["100"]["sources"] == {"statsbomb"}
    profile = build_profile(table["100"])
    assert profile["matches"] == 2
    assert profile["sources"] == ["statsbomb"]
    assert profile["confidence"] == profile_confidence(profile["actions"])


def test_no_source_leaves_provenance_empty():
    """Without a declared source nothing is invented: sources stay empty while
    the match count (real, observed) is still tracked."""
    profile = build_profile(_table()["100"])  # _table() passes no source
    assert profile["sources"] == []
    assert profile["matches"] == 1


def test_profile_sqlite_roundtrip():
    """Profiles persist to and read back from the player_profiles table,
    provenance and confidence included."""
    table = accumulate_player_stats(
        FIXTURE["events"], FIXTURE["home_team"], FIXTURE["away_team"], source="statsbomb"
    )
    profiles = [build_profile(rec) for rec in table.values()]
    conn = fie_db.connect(":memory:")
    fie_db.init_schema(conn)
    fie_db.insert_player_profiles(conn, profiles)
    n = conn.execute("SELECT COUNT(*) FROM player_profiles").fetchone()[0]
    assert n == 2
    row = conn.execute(
        "SELECT goals, shots, matches, sources, confidence "
        "FROM player_profiles WHERE player_id = '100'"
    ).fetchone()
    assert row[:2] == (1, 2)
    assert row[2] == 1 and row[3] == "statsbomb"           # provenance persisted
    assert row[4] == profile_confidence(_table()["100"]["actions"])


def test_profile_team_is_the_real_team_name():
    """A profile's team is the real team name, never the HOME/AWAY side."""
    table = _table()
    assert table["100"]["team"] not in ("HOME", "AWAY")
