"""C.10 — Confidence engine (Section 10)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fie.confidence import confidence

# A "perfect" set of inputs used as the baseline for the monotonicity tests.
PERFECT = dict(
    n_events=40,
    source_quality=1.0,
    source_agreement=1.0,
    regime_instability=0.0,
    similar_cases=50,
)


@given(
    n_events=st.floats(min_value=-10, max_value=200),
    source_quality=st.floats(min_value=-1, max_value=2),
    source_agreement=st.floats(min_value=-1, max_value=2),
    regime_instability=st.floats(min_value=-1, max_value=2),
    similar_cases=st.floats(min_value=-10, max_value=200),
)
def test_confidence_bounded(n_events, source_quality, source_agreement,
                            regime_instability, similar_cases):
    """T-10-01: output always in [0, 1] even for out-of-range raw values."""
    c = confidence(n_events, source_quality, source_agreement,
                   regime_instability, similar_cases)
    assert 0.0 <= c <= 1.0


def test_monotonic_in_n_events():
    """T-10-02: more data never lowers confidence (all else fixed)."""
    values = [confidence(**{**PERFECT, "n_events": n}) for n in range(0, 60, 5)]
    assert all(b >= a - 1e-12 for a, b in zip(values, values[1:]))


def test_monotonic_in_positive_factors():
    """T-10-03: monotonic in source_quality, source_agreement, similar_cases."""
    for factor, span in (
        ("source_quality", [i / 10 for i in range(11)]),
        ("source_agreement", [i / 10 for i in range(11)]),
        ("similar_cases", list(range(0, 60, 5))),
    ):
        values = [confidence(**{**PERFECT, factor: v}) for v in span]
        assert all(b >= a - 1e-12 for a, b in zip(values, values[1:])), factor


def test_monotonic_decreasing_in_instability():
    """T-10-04: monotonic decreasing in regime_instability."""
    values = [confidence(**{**PERFECT, "regime_instability": v / 10}) for v in range(11)]
    assert all(b <= a + 1e-12 for a, b in zip(values, values[1:]))


def test_one_zero_factor_collapses():
    """T-10-05: one factor at zero collapses confidence near zero."""
    c = confidence(**{**PERFECT, "n_events": 0})
    assert c < 0.05


def test_geometric_below_arithmetic():
    """T-10-06: geometric mean is measurably lower than the arithmetic mean."""
    factors = [1.0, 1.0, 1.0, 1.0, 0.2]  # one bad factor
    geometric = confidence(
        n_events=40, source_quality=1.0, source_agreement=1.0,
        regime_instability=0.0, similar_cases=10,  # 10/50 = 0.2 -> f_history
    )
    arithmetic = sum(factors) / len(factors)
    assert geometric < arithmetic
