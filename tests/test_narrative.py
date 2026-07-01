"""C.15 — Narrative Intelligence (Section 15)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fie.narrative import (
    classify,
    collective_state,
    divergence,
    opinion_to_hypothesis,
    update_credibility,
    update_narrative_memory,
    verify,
)
from tests.conftest import MULTI_SEEDS
from tests.generators import narrative_pattern_world, narrative_world


@pytest.mark.parametrize(
    "text",
    ["He was awful tonight", "jogador muito ruim", "the striker looks finished",
     "estava apagado o jogo todo"],
)
def test_negative_words_worse(text):
    """T-15-01: a known negative word -> direction 'worse' (EN and PT fixtures)."""
    assert opinion_to_hypothesis(text, "player")["direction"] == "worse"


def test_positive_words_better():
    """T-15-01 (companion): positive words -> 'better'."""
    assert opinion_to_hypothesis("brilliant, decisive display", "p")["direction"] == "better"
    assert opinion_to_hypothesis("jogo brilhante e decisivo", "p")["direction"] == "better"


@pytest.mark.parametrize(
    "direction,z,expected",
    [
        ("same", 0.3, "Confirmed"),
        ("same", 0.5, "Confirmed"),        # boundary, inclusive
        ("same", 0.6, "Not confirmed"),
        ("same", 1.5, "Not confirmed"),    # boundary, not yet contradicted
        ("same", 1.6, "Strongly contradicted"),
        ("same", 2.0, "Strongly contradicted"),
    ],
)
def test_classify_same_boundaries(direction, z, expected):
    """T-15-02: classify('same', z) across the 0.5 / 1.5 thresholds."""
    assert classify(direction, z) == expected


def test_classify_directional():
    """T-15-03: classify('better', ±2.0) confirms / strongly contradicts."""
    assert classify("better", 2.0) == "Confirmed"
    assert classify("better", -2.0) == "Strongly contradicted"
    assert classify("worse", -2.0) == "Confirmed"


@pytest.mark.slow
@pytest.mark.parametrize("p", [0.2, 0.5, 0.7, 0.95])
def test_credibility_converges(p):
    """T-15-04: a source's credibility converges to its true hit rate."""
    labels = narrative_world(true_accuracy=p, n_opinions=20_000, seed=MULTI_SEEDS[0])
    source = {}
    for label in labels:
        update_credibility(source, label)
    assert abs(source["weight"] - p) < 0.02


@given(a=st.floats(-100, 100), b=st.floats(-100, 100))
def test_divergence_symmetric_nonnegative(a, b):
    """T-15-05: divergence is symmetric and non-negative."""
    assert divergence(a, b) >= 0
    assert divergence(a, b) == divergence(b, a)


def test_collective_state_overreaction_true():
    """T-15-06: emotion=10, reality=80, threshold=40 -> overreaction True."""
    assert collective_state(10, 80, threshold=40)["overreaction"] is True


def test_collective_state_overreaction_false():
    """T-15-07: emotion=55, reality=80, threshold=40 -> overreaction False."""
    assert collective_state(55, 80, threshold=40)["overreaction"] is False


@given(
    base=st.floats(0, 100),
    div=st.floats(0, 100),
    shift=st.floats(-30, 30),
)
def test_overreaction_pure_function_of_divergence(base, div, shift):
    """T-15-08: overreaction depends only on abs(emotion-reality) > threshold."""
    a = collective_state(base, base + div, threshold=40)["overreaction"]
    b = collective_state(base + shift, base + shift + div, threshold=40)["overreaction"]
    assert a == b


@pytest.mark.slow
def test_narrative_memory_converges():
    """T-15-09: a recurring pattern's reliability converges to its true rate.

    Reproduces the spec's '18% cliché' reference; convergence to ±0.02 needs more
    than the 200-game illustration, so we use a larger draw with the same rate.
    """
    draws = narrative_pattern_world(true_rate=0.18, n_games=5_000, seed=MULTI_SEEDS[0])
    memory = {}
    for confirmed in draws:
        update_narrative_memory(memory, "team_X_collapses_late", confirmed)
    assert abs(memory["team_X_collapses_late"]["rate"] - 0.18) < 0.02


def test_verify_handles_non_finite():
    """T-15-10: verify() on a NaN real value never crashes or false-confirms."""
    hyp = {"target": "p", "aspect": "finishing", "direction": "better"}
    assert verify(hyp, real=math.nan, ref_mean=0.5, ref_std=0.1) == "Not confirmed"
    assert verify(hyp, real=1.0, ref_mean=0.5, ref_std=0.0) == "Not confirmed"
    assert verify(hyp, real=math.inf, ref_mean=0.5, ref_std=0.1) == "Not confirmed"
