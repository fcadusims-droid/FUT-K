"""C.8 — Prediction engine (Section 8)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fie.events import Event, State
from fie.prediction import (
    BASE_RATE,
    Params,
    poisson_at_least,
    prob_event_within,
    prob_next_goal,
    rates,
)
from tests.conftest import MULTI_SEEDS, SEED
from tests.generators import (
    simulate_first_scorer,
    simulate_goal_in_window,
    simulate_goals_per_match,
)


@given(lmbda=st.floats(min_value=0, max_value=20))
def test_poisson_at_least_zero(lmbda):
    """T-08-01: poisson_at_least(λ, 0) == 1.0 for any λ."""
    assert poisson_at_least(lmbda, 0) == 1.0


@given(lmbda=st.floats(min_value=0, max_value=20))
def test_poisson_at_least_one(lmbda):
    """T-08-02: poisson_at_least matches 1 - e^-λ for k=1."""
    assert math.isclose(poisson_at_least(lmbda, 1), 1 - math.exp(-lmbda), abs_tol=1e-12)


@pytest.mark.slow
def test_goal_in_window_matches_simulation():
    """T-08-03: goal-in-window formula matches the simulated frequency."""
    lam_home = lam_away = BASE_RATE
    formula = prob_event_within(lam_home + lam_away, 10)
    empirical = simulate_goal_in_window(lam_home, lam_away, 10, n=100_000, seed=SEED)
    assert abs(formula - empirical) < 0.005  # within 0.5 percentage point
    # Exact closed form for λ_total=0.03 over 10 min is 1 - e^-0.3 = 0.2592; the
    # spec's "≈27–28%" is a loose approximation of this same quantity.
    assert 0.25 < formula < 0.27


@pytest.mark.slow
def test_next_goal_matches_first_scorer():
    """T-08-04: prob_next_goal matches the empirical 'who scores first' share."""
    lam_home, lam_away = 0.02, 0.01
    expected = prob_next_goal(lam_home, lam_away)["HOME"]
    empirical = simulate_first_scorer(lam_home, lam_away, n=100_000, seed=SEED)
    assert abs(expected - empirical) < 0.005


@given(
    lam_home=st.floats(min_value=0, max_value=1),
    lam_away=st.floats(min_value=0, max_value=1),
)
def test_next_goal_sums_to_one(lam_home, lam_away):
    """T-08-05: prob_next_goal sums to 1 (or {0.5, 0.5} when λ=0)."""
    p = prob_next_goal(lam_home, lam_away)
    assert math.isclose(p["HOME"] + p["AWAY"], 1.0, abs_tol=1e-9)


@pytest.mark.slow
def test_base_rate_reproduces_goals_per_match():
    """T-08-06: BASE_RATE=0.015 reproduces ~2.7 goals/match."""
    mean_goals = simulate_goals_per_match(BASE_RATE, BASE_RATE, 90, n=80_000, seed=SEED)
    assert 2.6 <= mean_goals <= 2.8


red_event = st.builds(
    lambda team, minute: Event(match_id="t", minute=float(minute), team=team, type="red_card"),
    st.sampled_from(["HOME", "AWAY"]),
    st.floats(min_value=0, max_value=90),
)


@given(
    minute=st.floats(min_value=0, max_value=90),
    hg=st.integers(min_value=0, max_value=5),
    ag=st.integers(min_value=0, max_value=5),
    reds=st.lists(red_event, max_size=6),
    base_rate=st.floats(min_value=0, max_value=0.1),
)
@settings(max_examples=500)
def test_rates_never_negative(minute, hg, ag, reds, base_rate):
    """T-08-07: rates() never returns a negative λ, even at multiplier extremes."""
    state = State(minute=minute, home_goals=hg, away_goals=ag)
    params = Params(base_rate=base_rate)
    lam_home, lam_away = rates(state, reds, params)
    assert lam_home >= 0.0 and lam_away >= 0.0


@pytest.mark.slow
@pytest.mark.parametrize("seed", MULTI_SEEDS)
def test_biased_rate_is_detectably_different(seed):
    """T-08-08: a biased λ (×1.4) produces a measurably different goal rate."""
    unbiased = simulate_goals_per_match(BASE_RATE, BASE_RATE, 90, n=40_000, seed=seed)
    biased = simulate_goals_per_match(1.4 * BASE_RATE, 1.4 * BASE_RATE, 90, n=40_000, seed=seed)
    # ~40% more goals — far outside sampling noise, so T-20-02 has a real effect.
    assert biased > unbiased + 0.5
