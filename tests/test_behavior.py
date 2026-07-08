"""Phase D — behavioral indices from event sequences, with honest abstention."""

from __future__ import annotations

from fie.behavior import ABSTAINED_ALWAYS, behavioral_profile
from fie.events import Event


def _profile(**kw):
    base = {"player_id": "p1", "pass_accuracy": 0.85, "turnover_rate": 0.03,
            "actions": 120, "dribbles": 8, "dribble_success": 0.6, "confidence": 0.7}
    base.update(kw)
    return base


def test_decision_stability_and_pressure_resistance_from_profile():
    prof = _profile()
    out = behavioral_profile(prof)
    assert 0.0 <= out["decision_stability"] <= 1.0
    # High pass accuracy + low turnovers -> high stability.
    assert out["decision_stability"] > 0.7
    assert out["pressure_resistance"] == 0.6            # take-on success


def test_pressure_resistance_abstains_without_enough_dribbles():
    out = behavioral_profile(_profile(dribbles=2))
    assert out["pressure_resistance"] is None
    assert "pressure_resistance" in out["abstained"]


def test_aggression_control_reads_fouls_and_cards():
    events = [
        Event("m1", 10.0, "HOME", "pass", player_id="p1"),
        Event("m1", 20.0, "HOME", "foul", player_id="p1"),
        Event("m1", 30.0, "HOME", "yellow_card", player_id="p1"),
    ]
    clean = behavioral_profile(_profile(actions=120), events=[
        Event("m1", 10.0, "HOME", "pass", player_id="p1")])
    rough = behavioral_profile(_profile(actions=120), events=events)
    # A player with fouls/cards controls aggression less than a clean one.
    assert rough["aggression_control"] < clean["aggression_control"]
    assert 0.0 <= rough["aggression_control"] <= 1.0


def test_resilience_needs_conceded_and_activity_before():
    events = [Event("m1", float(t), "HOME", "pass", player_id="p1")
              for t in (10, 20, 30, 60, 70, 80)]
    # Team conceded at 45'; the player stays involved after -> resilient reading.
    out = behavioral_profile(_profile(), events=events, conceded_minutes=[45.0])
    assert out["resilience_index"] is not None
    # No conceded goal -> abstain.
    assert behavioral_profile(_profile(), events=events)["resilience_index"] is None


def test_confidence_curve_is_an_involvement_series():
    events = [Event("m1", float(t), "HOME", "pass", player_id="p1")
              for t in (5, 6, 40, 88)]
    out = behavioral_profile(_profile(), events=events)
    curve = out["confidence_curve"]
    assert isinstance(curve, list) and curve
    assert sum(w["actions"] for w in curve) == 4       # every action bucketed


def test_unsupported_indices_are_always_abstained_with_a_reason():
    out = behavioral_profile(_profile())
    for name in ("leadership_index", "recovery_behavior", "tactical_discipline"):
        assert name in out["abstained"]
        assert out["abstained"][name] == ABSTAINED_ALWAYS[name]


def test_behavioral_profile_is_deterministic():
    prof = _profile()
    events = [Event("m1", 10.0, "HOME", "foul", player_id="p1")]
    a = behavioral_profile(prof, events=events)
    b = behavioral_profile(dict(prof), events=list(events))
    assert a == b
