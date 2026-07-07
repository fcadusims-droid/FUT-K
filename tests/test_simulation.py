"""Future Simulation Engine — deterministic, calibrated, honest by construction."""

from __future__ import annotations

from fie.events import Event, State
from fie.prediction import Params, rates
from fie.prediction import prob_event_within
from fie.simulation import lane_weights, simulate_forward


def _state(minute=70.0, hg=1, ag=1):
    return State(match_id="m", minute=minute, home_goals=hg, away_goals=ag)


def _events():
    # A few located attacking actions, HOME favouring the left lane.
    return [
        Event(match_id="m", minute=62.0, team="HOME", type="shot", x=90.0, y=72.0),
        Event(match_id="m", minute=64.0, team="HOME", type="corner", x=99.0, y=78.0),
        Event(match_id="m", minute=66.0, team="HOME", type="shot_on_target", x=88.0, y=70.0),
        Event(match_id="m", minute=61.0, team="AWAY", type="shot", x=85.0, y=20.0),
    ]


def test_determinism_same_seed_same_output():
    st, ev = _state(), _events()
    a = simulate_forward(st, ev, horizon_minutes=20, n_sims=2000, seed=7)
    b = simulate_forward(st, ev, horizon_minutes=20, n_sims=2000, seed=7)
    assert a == b
    # A different seed generally differs (not a hard guarantee, but overwhelming).
    c = simulate_forward(st, ev, horizon_minutes=20, n_sims=2000, seed=8)
    assert c["scorelines"] != a["scorelines"] or c["goal_prob"] != a["goal_prob"]


def test_monte_carlo_converges_to_analytic_poisson():
    # The honest test: the simulated P(>=1 goal in horizon) must match the
    # closed-form Poisson from the SAME calibrated rates, within MC error.
    st, ev = _state(), _events()
    params = Params()
    lam_home, lam_away = rates(st, ev, params)
    horizon = 15.0
    # Closed-form P(>=1 goal) over the horizon from the same calibrated rates.
    analytic_any = prob_event_within(lam_home + lam_away, horizon)
    sim = simulate_forward(st, ev, params, horizon_minutes=horizon,
                           n_sims=20000, seed=1)
    assert abs(sim["goal_prob"]["any"] - analytic_any) < 0.02
    # Expected goals should match lambda * horizon too.
    assert abs(sim["expected_goals"]["home"] - lam_home * horizon) < 0.05


def test_horizon_is_respected_never_hardcoded():
    st, ev = _state(minute=93.0), _events()
    # Almost no time left -> almost no chance of a goal, few/no windows.
    tiny = simulate_forward(st, ev, horizon_minutes=1.5, n_sims=5000, seed=3)
    big = simulate_forward(st, ev, horizon_minutes=30.0, n_sims=5000, seed=3)
    assert tiny["horizon_minutes"] == 1.5
    assert tiny["goal_prob"]["any"] < big["goal_prob"]["any"]
    # Zero remaining time -> nothing to simulate, honestly empty.
    none = simulate_forward(st, ev, horizon_minutes=0.0, n_sims=5000, seed=3)
    assert none["goal_prob"]["any"] == 0.0 and none["opportunity_windows"] == []


def test_lane_windows_reflect_recent_real_locations():
    st, ev = _state(), _events()
    lw = lane_weights(ev, "HOME", st.minute, Params().tau)
    # HOME's recent attacks were all on the left -> left is the dominant lane.
    assert lw["left"] > lw["central"] and lw["left"] > lw["right"]
    sim = simulate_forward(st, ev, horizon_minutes=25, n_sims=8000, seed=5)
    home_windows = [w for w in sim["opportunity_windows"] if w["team"] == "HOME"]
    assert home_windows, "expected at least one HOME opportunity window"
    # The most probable HOME window is on the left lane it has been using.
    assert home_windows[0]["lane"] == "left"
    assert home_windows[0]["eta_seconds"] >= 0


def test_simulation_is_leakage_free_erase_the_future():
    """The 73:15 discipline applied to the Future Sim: erasing every event
    after the simulation minute must leave the output byte-identical, because
    every read (momentum, cards, lanes) self-filters at ``state.minute``."""
    import json

    future = [
        Event(match_id="m", minute=80.0, team="AWAY", type="goal", x=95.0, y=40.0),
        Event(match_id="m", minute=84.0, team="AWAY", type="shot_on_target", x=90.0, y=45.0),
        Event(match_id="m", minute=88.0, team="HOME", type="red_card"),
    ]
    full = _events() + future
    truncated = [e for e in full if e.minute <= 70.0]

    kw = dict(horizon_minutes=25.0, n_sims=400, seed=7, regime="NORMAL")
    with_future = simulate_forward(_state(70.0), full, Params(), **kw)
    without_future = simulate_forward(_state(70.0), truncated, Params(), **kw)
    assert json.dumps(with_future, sort_keys=True) == \
        json.dumps(without_future, sort_keys=True)
