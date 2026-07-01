"""C.19 — Explanatory Intelligence (Section 19)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fie.explain import explain


def test_high_confidence_no_hedge():
    """T-19-01: confidence > 0.66 -> no hedge text."""
    out = explain("goal prob rising", None, [], ["sustained pressure"], [], confidence=0.8)
    assert out["note"] == ""


def test_low_confidence_hedge():
    """T-19-02: confidence <= 0.66 -> hedge text present (at and below boundary)."""
    assert explain("x", None, [], [], [], confidence=0.66)["note"] != ""
    assert explain("x", None, [], [], [], confidence=0.4)["note"] != ""


text_list = st.lists(st.text(min_size=1, max_size=8), max_size=5)


@given(
    change_present=st.booleans(),
    mechanisms=text_list,
    causes=text_list,
    drivers=text_list,
    confidence=st.floats(0, 1),
)
def test_because_length(change_present, mechanisms, causes, drivers, confidence):
    """T-19-03: because length == (1 if change else 0) + len(all evidence lists)."""
    change = {"minute": 31} if change_present else None
    out = explain("claim", change, causes, mechanisms, drivers, confidence)
    expected = (1 if change_present else 0) + len(mechanisms) + len(causes) + len(drivers)
    assert len(out["because"]) == expected
