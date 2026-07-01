"""C.16 — Consensus engine (Section 16)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fie.consensus import consensus


def test_majority_with_agreement():
    """T-16-01: three sources agree vs one dissenter -> majority, agreement ~0.875."""
    readings = [
        {"claim": "chance_created", "weight": 0.9},
        {"claim": "chance_created", "weight": 0.7},
        {"claim": "chance_created", "weight": 0.5},
        {"claim": "ordinary_attack", "weight": 0.3},
    ]
    result = consensus(readings)
    assert result["claim"] == "chance_created"
    assert abs(result["agreement"] - 0.875) < 0.01


reading = st.fixed_dictionaries(
    {"claim": st.sampled_from(["a", "b", "c"]), "weight": st.floats(0, 5)}
)


@given(readings=st.lists(reading, max_size=20))
def test_agreement_bounded(readings):
    """T-16-02: agreement is always in [0, 1]."""
    result = consensus(readings)
    assert 0.0 <= result["agreement"] <= 1.0


def test_empty_readings():
    """T-16-03: empty readings -> {claim: None, agreement: 0.0}."""
    assert consensus([]) == {"claim": None, "agreement": 0.0}


def test_tie_break_is_deterministic():
    """T-16-04: a 50/50 tie -> agreement 0.5 and the documented lexicographic claim."""
    readings = [
        {"claim": "bbb", "weight": 1.0},
        {"claim": "aaa", "weight": 1.0},
    ]
    result = consensus(readings)
    assert result["claim"] == "aaa"  # lexicographically smallest on a tie
    assert abs(result["agreement"] - 0.5) < 1e-12
