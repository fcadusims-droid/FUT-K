"""C.14 — Tactical & Collective Intelligence (Section 14).

Per the plan's note, the decision rules are pinned down explicitly in
``fie.tactical`` and tested against *those* rules.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fie.events import Event
from fie.tactical import (
    cohesion,
    detect_tactic,
    fluidity,
    team_robustness,
)


def _ev(minute, x, team="HOME"):
    return Event(match_id="t", minute=float(minute), team=team, type="pass", x=float(x))


def test_low_block_detected():
    """T-14-01: all events in the team's defensive third -> low_block."""
    events = [_ev(m, x) for m, x in [(10, 8), (12, 15), (14, 20), (16, 12)]]
    assert detect_tactic(events, "HOME", attack_right=True) == "low_block"


def test_counter_attack_detected():
    """T-14-02: a fast defensive-third -> attacking-third transition -> counter."""
    events = [_ev(50.0, 10), _ev(50.1, 92)]  # 6-second transition across the pitch
    assert detect_tactic(events, "HOME", attack_right=True) == "counter_attack"


def test_star_network_less_robust_than_distributed():
    """T-14-03: a star network is less robust than an evenly distributed one."""
    star = {
        ("HUB", "A"): {"weight": 10, "chances": 0},
        ("HUB", "B"): {"weight": 10, "chances": 0},
        ("HUB", "C"): {"weight": 10, "chances": 0},
        ("HUB", "D"): {"weight": 10, "chances": 0},
    }
    ring = {
        ("A", "B"): {"weight": 10, "chances": 0},
        ("B", "C"): {"weight": 10, "chances": 0},
        ("C", "D"): {"weight": 10, "chances": 0},
        ("D", "A"): {"weight": 10, "chances": 0},
    }
    assert team_robustness(star) < team_robustness(ring)


nodes = st.sampled_from(["A", "B", "C", "D", "E"])
network_strategy = st.dictionaries(
    st.tuples(nodes, nodes).filter(lambda e: e[0] != e[1]),
    st.fixed_dictionaries({"weight": st.integers(1, 20),
                           "chances": st.integers(0, 5)}),
    max_size=15,
)


@given(network=network_strategy)
def test_collective_metrics_bounded(network):
    """T-14-04: cohesion / fluidity metrics stay within [0, 1]."""
    assert 0.0 <= cohesion(network) <= 1.0
    assert 0.0 <= fluidity(network) <= 1.0
    assert 0.0 <= team_robustness(network) <= 1.0


def test_tactical_geometry_reads_real_positions():
    """Block height, lanes and territory come only from located events."""
    from fie.events import Event
    from fie.tactical import tactical_geometry

    def ev(minute, x, y, team, etype="pass"):
        return Event(match_id="t", minute=float(minute), team=team, type=etype,
                     x=float(x), y=float(y))

    # HOME playing high (x~85) and attacking down the left (y high); AWAY deep.
    events = [
        ev(60, 82, 70, "HOME", "shot"), ev(62, 88, 74, "HOME", "corner"),
        ev(64, 80, 72, "HOME", "shot_on_target"), ev(63, 86, 68, "HOME"),
        ev(61, 25, 40, "AWAY"), ev(65, 30, 45, "AWAY"),
    ]
    g = tactical_geometry(events, minute=66.0, window=15.0)
    assert g["teams"]["HOME"]["block_x"] > g["teams"]["AWAY"]["block_x"]  # higher line
    assert g["teams"]["HOME"]["lanes"]["left"] > g["teams"]["HOME"]["lanes"]["right"]
    assert g["territory_home"] > 0.5           # HOME has the recent pressure
    assert g["top_lane"] == {"team": "HOME", "lane": "left",
                             "share": g["teams"]["HOME"]["lanes"]["left"]}
    # No located events in-window -> neutral, never a crash.
    empty = tactical_geometry([], minute=10.0)
    assert empty["territory_home"] == 0.5 and empty["teams"]["HOME"]["actions"] == 0
