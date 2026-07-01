"""Section 12 — player DNA profiling (offline, deterministic)."""

from __future__ import annotations

import json
import math
import pathlib

import pytest

from fie import db as fie_db
from fie.profiling import MIN_ACTIONS, build_profile, profile_avatar, real_archetype
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


def test_profile_sqlite_roundtrip():
    """Profiles persist to and read back from the player_profiles table."""
    profiles = [build_profile(rec) for rec in _table().values()]
    conn = fie_db.connect(":memory:")
    fie_db.init_schema(conn)
    fie_db.insert_player_profiles(conn, profiles)
    n = conn.execute("SELECT COUNT(*) FROM player_profiles").fetchone()[0]
    assert n == 2
    row = conn.execute(
        "SELECT goals, shots FROM player_profiles WHERE player_id = '100'"
    ).fetchone()
    assert row == (1, 2)
