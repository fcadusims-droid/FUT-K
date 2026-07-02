"""External-benchmark models (Elo, attack/defense Poisson) — offline."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from fie.ratings import (
    Elo,
    PoissonAD,
    TrailingFrequencies,
    brier_multi,
    implied_1x2,
    logloss_multi,
    outcome_index,
)


def test_outcome_index():
    assert outcome_index(2, 1) == 0
    assert outcome_index(1, 1) == 1
    assert outcome_index(0, 3) == 2


def test_elo_updates_toward_winner():
    elo = Elo()
    before = elo.rating["A"]
    elo.update("A", "B", 3, 0)
    assert elo.rating["A"] > before
    assert elo.rating["B"] < before
    # Winner is now favored even away (rating gap exceeds home advantage after
    # repeated wins).
    for _ in range(5):
        elo.update("A", "B", 2, 0)
    assert elo.expected_home("B", "A") < 0.5


def test_elo_1x2_sums_to_one():
    elo = Elo()
    p = elo.predict_1x2("A", "B", draw_rate=0.25)
    assert math.isclose(sum(p), 1.0, abs_tol=1e-9)
    assert p[1] == 0.25


def test_poisson_ad_sums_to_one_and_learns_strength():
    pad = PoissonAD()
    p0 = pad.predict_1x2("Strong", "Weak")
    assert math.isclose(sum(p0), 1.0, abs_tol=1e-9)
    # Feed a season where Strong hammers everyone and Weak concedes a lot.
    for _ in range(15):
        pad.update("Strong", "Weak", 3, 0)
        pad.update("Weak", "Other", 0, 2)
        pad.update("Other", "Strong", 0, 2)
    p = pad.predict_1x2("Strong", "Weak")
    assert p[0] > 0.6  # Strong at home vs Weak is now a heavy favorite
    lam_h, lam_a = pad.rates("Strong", "Weak")
    assert lam_h > lam_a


def test_implied_1x2_removes_margin():
    # A typical over-round book: implied sums to 1 after normalization.
    p = implied_1x2(1.90, 3.50, 4.20)
    assert math.isclose(sum(p), 1.0, abs_tol=1e-12)
    assert p[0] > p[1] > p[2]


@given(
    ph=st.floats(0.01, 0.98),
    pd=st.floats(0.01, 0.98),
)
def test_multiclass_scores_bounded(ph, pd):
    if ph + pd >= 0.99:
        return
    probs = (ph, pd, 1 - ph - pd)
    for idx in (0, 1, 2):
        assert 0.0 <= brier_multi(probs, idx) <= 2.0
        assert logloss_multi(probs, idx) >= 0.0


def test_perfect_prediction_scores_zero():
    assert brier_multi((1.0, 0.0, 0.0), 0) == 0.0
    assert logloss_multi((1.0, 0.0, 0.0), 0) < 1e-12


def test_trailing_frequencies_track():
    tf = TrailingFrequencies()
    for _ in range(50):
        tf.update(1, 0)  # all home wins
    p = tf.predict_1x2()
    assert p[0] > 0.9
    assert math.isclose(sum(p), 1.0, abs_tol=1e-9)


def test_walk_forward_no_future_influence():
    """A model's prediction for match t is unchanged by later matches."""
    elo = Elo()
    elo.update("A", "B", 2, 0)
    pred_before = elo.predict_1x2("A", "C", draw_rate=0.25)
    # A later match between other teams must not change A-vs-C's prediction.
    elo2 = Elo()
    elo2.update("A", "B", 2, 0)
    elo2.update("D", "E", 0, 5)
    assert elo2.predict_1x2("A", "C", draw_rate=0.25) == pred_before
