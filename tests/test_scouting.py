"""Scout AI foundations — similarity, percentiles, age handling, scout index."""

from __future__ import annotations

import math

from fie.scouting import (
    age_factor,
    age_on,
    cosine,
    percentile,
    profile_vector,
    scout_index,
    similar_players,
)

FINISHER = {"pass_accuracy": 0.72, "progressive_pass_share": 0.10, "key_pass_rate": 0.01,
            "shot_share": 0.12, "turnover_rate": 0.05, "goals": 9, "assists": 1,
            "actions": 300}
CREATOR = {"pass_accuracy": 0.88, "progressive_pass_share": 0.30, "key_pass_rate": 0.06,
           "shot_share": 0.02, "turnover_rate": 0.03, "goals": 1, "assists": 8,
           "actions": 600}
FINISHER_TWIN = {**FINISHER, "goals": 8, "actions": 280}


def test_profile_vector_normalized_and_deterministic():
    v = profile_vector(FINISHER)
    assert len(v) == 7 and all(0.0 <= x <= 1.0 for x in v)
    assert v == profile_vector(dict(FINISHER))  # pure function


def test_vector_accepts_stored_column_name():
    """Backend rows store 'progressive_pass'; the engine key is *_share."""
    a = profile_vector({**CREATOR})
    renamed = {k: v for k, v in CREATOR.items() if k != "progressive_pass_share"}
    renamed["progressive_pass"] = CREATOR["progressive_pass_share"]
    assert profile_vector(renamed) == a


def test_similarity_ranks_the_behavioral_twin_first():
    ranked = similar_players(FINISHER, {"twin": FINISHER_TWIN, "creator": CREATOR})
    assert [pid for pid, _ in ranked] == ["twin", "creator"]
    assert ranked[0][1] > ranked[1][1]
    assert math.isclose(cosine(profile_vector(FINISHER), profile_vector(FINISHER)), 1.0)


def test_percentile_midrank():
    pop = [1.0, 2.0, 3.0, 4.0]
    assert percentile(5.0, pop) == 1.0
    assert percentile(0.0, pop) == 0.0
    assert percentile(2.0, pop) == (1 + 0.5) / 4      # one below + half the tie
    assert percentile(0.7, []) == 0.5                  # unknown cohort -> neutral


def test_age_on_and_unknown():
    assert age_on("2007-07-13", "2026-07-13") == 19.0
    assert age_on(None, "2026-01-01") is None
    assert age_on("not-a-date", "2026-01-01") is None


def test_age_factor_bounds_and_neutral_unknown():
    assert age_factor(17.0) == 1.15
    assert age_factor(35.0) == 0.85
    assert age_factor(None) == 1.0                     # never a guessed bonus
    mid = age_factor(25.5)
    assert 0.85 < mid < 1.15


def test_scout_index_monotonic_and_transparent():
    high = scout_index({"attack": 0.9, "creation": 0.8}, confidence=0.9, age=18.0)
    low = scout_index({"attack": 0.3, "creation": 0.2}, confidence=0.9, age=18.0)
    thin = scout_index({"attack": 0.9, "creation": 0.8}, confidence=0.1, age=18.0)
    old = scout_index({"attack": 0.9, "creation": 0.8}, confidence=0.9, age=33.0)
    assert high["score"] > low["score"]                # better percentiles win
    assert high["score"] > thin["score"]               # evidence volume matters
    assert high["score"] > old["score"]                # runway matters when age known
    assert 0.0 <= high["score"] <= 100.0
    assert set(high["components"]) == {"attack", "creation"}


def test_scout_index_age_unknown_is_honest():
    r = scout_index({"attack": 0.5}, confidence=0.5, age=None)
    assert r["age"] is None and r["age_factor"] == 1.0
    assert "age unknown" in r["note"]
    assert "Not a trained potential prediction" in r["note"]
