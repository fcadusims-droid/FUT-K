"""Strategic Assistant — decisions ranked by simulated win probability."""

from __future__ import annotations

from fie.events import Event, State
from fie.strategy import APPROACHES, evaluate_decisions


def _events():
    return [
        Event(match_id="m", minute=60.0, team="HOME", type="shot", x=90.0, y=60.0),
        Event(match_id="m", minute=64.0, team="HOME", type="corner", x=99.0, y=70.0),
        Event(match_id="m", minute=61.0, team="AWAY", type="shot", x=85.0, y=40.0),
    ]


def test_decisions_ranked_and_deterministic():
    st = State(match_id="m", minute=70.0, home_goals=1, away_goals=1)
    a = evaluate_decisions(st, _events(), team="HOME", horizon_minutes=20,
                           n_sims=4000, seed=1)
    b = evaluate_decisions(st, _events(), team="HOME", horizon_minutes=20,
                           n_sims=4000, seed=1)
    assert a == b                                   # deterministic
    assert len(a["decisions"]) == len(APPROACHES)
    # Sorted by win-probability gain, best first.
    deltas = [d["delta_win"] for d in a["decisions"]]
    assert deltas == sorted(deltas, reverse=True)
    # "keep" is the reference: its delta is exactly 0.
    keep = next(d for d in a["decisions"] if d["key"] == "keep")
    assert keep["delta_win"] == 0.0


def test_when_leading_defending_beats_attacking():
    # HOME leads by one with little time left: sitting deeper should protect the
    # win at least as well as committing forward.
    st = State(match_id="m", minute=85.0, home_goals=2, away_goals=1)
    res = evaluate_decisions(st, _events(), team="HOME", horizon_minutes=8,
                             n_sims=12000, seed=3)
    by_key = {d["key"]: d for d in res["decisions"]}
    assert by_key["defend"]["win"] >= by_key["attack"]["win"]
    # Win/draw/loss form a proper distribution.
    for d in res["decisions"]:
        assert abs(d["win"] + d["draw"] + d["loss"] - 1.0) < 0.02


def test_when_chasing_attacking_raises_win_prob():
    # HOME trails by one late: committing forward should raise its win chance
    # above keeping the current shape.
    st = State(match_id="m", minute=80.0, home_goals=0, away_goals=1)
    res = evaluate_decisions(st, _events(), team="HOME", horizon_minutes=15,
                             n_sims=12000, seed=5)
    by_key = {d["key"]: d for d in res["decisions"]}
    assert by_key["attack"]["win"] > by_key["keep"]["win"]
    assert res["recommended"] in ("attack", "control", "defend", "keep")
