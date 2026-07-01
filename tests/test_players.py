"""C.12 — Individual Intelligence (Section 12)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fie.events import Event, State
from fie.players import (
    archetype,
    avatar,
    collective_rate,
    critical_links,
    decision_profile,
    goal_influence,
    passing_network,
    player_aware_lambda,
)
from fie.prediction import Params
from tests.conftest import MULTI_SEEDS
from tests.generators import simulate_on_off_influence


@dataclass
class Reception:
    zone: str
    next_action: str
    type: str = "reception"


@dataclass
class Pass:
    from_: str
    to: str
    success: bool = True
    created_chance: bool = False


# --------------------------------------------------------------------------- #
# decision_profile
# --------------------------------------------------------------------------- #
receptions = st.lists(
    st.builds(Reception, st.sampled_from(["box", "wing", "mid"]),
              st.sampled_from(["shot", "pass", "dribble", "drop"])),
    max_size=30,
)


@given(evs=receptions, zone=st.sampled_from(["box", "wing", "mid"]))
def test_decision_profile_sums_to_one(evs, zone):
    """T-12-01: decision_profile sums to 1.0, or all-zero when no data."""
    profile = decision_profile(evs, zone)
    total = sum(profile.values())
    assert abs(total - 1.0) < 1e-9 or total == 0.0


# --------------------------------------------------------------------------- #
# archetypes
# --------------------------------------------------------------------------- #
def test_finisher_archetype():
    """T-12-02: a shot-heavy quick-trigger profile -> finisher."""
    assert archetype({"shot_frequency": 0.9, "time_to_shot": 1.0}) == "finisher"


@pytest.mark.parametrize(
    "profile,expected",
    [
        ({"shot_frequency": 0.9, "time_to_shot": 1.0}, "finisher"),
        ({"progressive_pass": 0.2, "assist_frequency": 0.4, "shot_frequency": 0.1}, "creator"),
        ({"turnover_rate": 0.3, "hard_dribbles": 0.4}, "impulsive"),
        ({"risk": 0.05, "lateral_passes": 0.7}, "conservative"),
        ({}, "balanced"),
    ],
)
def test_all_archetypes_reachable(profile, expected):
    """T-12-03: each named archetype is reachable with a hand-built profile."""
    assert archetype(profile) == expected


# --------------------------------------------------------------------------- #
# influence
# --------------------------------------------------------------------------- #
@given(on=st.floats(-5, 5), off=st.floats(-5, 5))
def test_goal_influence_is_difference(on, off):
    """T-12-04: goal_influence is exactly lambda_on - lambda_off."""
    assert goal_influence(on, off) == on - off


@pytest.mark.slow
@pytest.mark.parametrize("seed", MULTI_SEEDS[:3])
@pytest.mark.parametrize("k", [0.7, 1.0, 1.5])
def test_on_off_recovers_injected_effect(k, seed):
    """T-12-05: on/off influence recovers a known injected factor within 5%."""
    lam_on, lam_off = simulate_on_off_influence(
        base_lambda=0.03, k=k, on_minutes=45, off_minutes=45,
        n_matches=20_000, seed=seed,
    )
    recovered = lam_on / lam_off
    assert abs(recovered - k) / k < 0.05


# --------------------------------------------------------------------------- #
# passing network
# --------------------------------------------------------------------------- #
def test_passing_network_counts_only_successful():
    """T-12-06: passing_network only counts successful passes."""
    passes = [
        Pass("A", "B", success=True),
        Pass("A", "B", success=False),
        Pass("B", "C", success=True),
    ]
    graph = passing_network(passes)
    assert graph[("A", "B")]["weight"] == 1
    assert graph[("B", "C")]["weight"] == 1
    assert ("A", "B") in graph and graph[("A", "B")]["weight"] != 2


def test_critical_links_top_k():
    """T-12-07: critical_links identifies the top-k highest-volume nodes."""
    graph = {
        ("HUB", "A"): {"weight": 10, "chances": 0},
        ("HUB", "B"): {"weight": 8, "chances": 0},
        ("HUB", "C"): {"weight": 6, "chances": 0},
        ("D", "E"): {"weight": 1, "chances": 0},
    }
    assert set(critical_links(graph, top=3)) == {"HUB", "A", "B"}


# --------------------------------------------------------------------------- #
# avatar
# --------------------------------------------------------------------------- #
@given(
    profile=st.dictionaries(
        st.sampled_from(list(avatar({}).keys())),
        st.floats(min_value=-100, max_value=100),
    )
)
def test_avatar_normalized(profile):
    """T-12-08: every avatar dimension is within [0, 1]."""
    for value in avatar(profile).values():
        assert 0.0 <= value <= 1.0


# --------------------------------------------------------------------------- #
# player-aware lambda
# --------------------------------------------------------------------------- #
def test_player_aware_reduces_to_collective():
    """T-12-09: player_aware_lambda == collective_rate with neutral factors."""
    state = State(minute=30, home_goals=0, away_goals=0)
    events = [Event("t", 25, "HOME", "shot"), Event("t", 28, "AWAY", "corner")]
    params = Params()
    base = collective_rate(state, "HOME", events, params)
    aware = player_aware_lambda(state, "HOME", events, params,
                                mult_lineup=1.0, network_bonus=1.0)
    assert aware == base
