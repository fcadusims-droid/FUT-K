"""C.18 — Causality Model (Section 18)."""

from __future__ import annotations

from fie.causality import likely_causes

ALL_ACTIVE = {
    "passes_received_rel": 0.5,
    "nearby_markers": 2,
    "changed_zone": True,
    "team_midfield_control": 0.3,
}
EXPECTED_ORDER = [
    "receiving fewer passes than usual",
    "closely marked by 2+ defenders",
    "moved to a different zone",
    "the team lost control of midfield",
]


def test_all_triggers_active():
    """T-18-01: all four triggers active -> all four causes, in documented order."""
    assert likely_causes(ALL_ACTIVE) == EXPECTED_ORDER


def test_no_triggers():
    """T-18-02: no triggers active -> empty list."""
    normal = {
        "passes_received_rel": 1.0,
        "nearby_markers": 0,
        "changed_zone": False,
        "team_midfield_control": 1.0,
    }
    assert likely_causes(normal) == []


def test_triggers_independent():
    """T-18-03: each trigger fires independently of the others."""
    keys = ["passes_received_rel", "nearby_markers", "changed_zone", "team_midfield_control"]
    for key, cause in zip(keys, EXPECTED_ORDER):
        features = {
            "passes_received_rel": 1.0,
            "nearby_markers": 0,
            "changed_zone": False,
            "team_midfield_control": 1.0,
        }
        features[key] = ALL_ACTIVE[key]
        assert likely_causes(features) == [cause]


def test_boundary_strict_less_than():
    """T-18-04: passes_received_rel exactly 0.7 does not trigger (strict <)."""
    features = {"passes_received_rel": 0.7}
    assert "receiving fewer passes than usual" not in likely_causes(features)
    features = {"passes_received_rel": 0.699}
    assert "receiving fewer passes than usual" in likely_causes(features)
