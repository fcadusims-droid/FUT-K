"""Phase C — lift engine outputs into the Dataset Fusion contract.

Predictions become PROBABILISTIC records, simulations SIMULATED, profiles and
embeddings DERIVED — each citing the model that produced it, deterministically,
and never confusable with an observed fact.
"""

from __future__ import annotations

import pytest

from fie.fusiondata import Context, IntegrityError, Layer, Provenance, make_record
from fie.knowledgemap import (
    embedding_record,
    prediction_records,
    profile_record,
    simulation_records,
)

MATCH = Context(match_id="m1", minute=73.0)


def test_prediction_records_are_probabilistic_and_cite_the_model():
    preds = {
        "goal_next_5min": 0.11, "goal_next_10min": 0.19,
        "goal_before_half": 0.4, "next_goal": {"home": 0.69, "away": 0.31},
    }
    recs = prediction_records(preds, MATCH, confidence=0.72)
    kinds = {r.kind for r in recs}
    assert kinds == {"pred_goal_next_5min", "pred_goal_next_10min",
                     "pred_goal_before_half", "pred_next_goal"}
    for r in recs:
        assert r.layer is Layer.PROBABILISTIC
        assert r.provenance.pipeline_version == "prediction/poisson"   # evidence
        assert r.temporal.confidence == 0.72
    ng = next(r for r in recs if r.kind == "pred_next_goal")
    assert ng.value == {"home": 0.69, "away": 0.31}


def test_simulation_records_are_simulated_and_reproducible():
    sim = {
        "seed": 42, "n_sims": 8000,
        "outcome": {"home_win": 0.5, "draw": 0.3, "away_win": 0.2},
        "expected_goals": {"home": 0.4, "away": 0.2},
        "goal_prob": {"any": 0.35},
        "scorelines": [{"score": "0-0", "prob": 0.6}],
        "opportunity_windows": [{"team": "HOME", "lane": "left", "probability": 0.3}],
    }
    recs = simulation_records(sim, MATCH)
    assert {r.kind for r in recs} == {
        "sim_outcome", "sim_expected_goals", "sim_goal_prob",
        "sim_scorelines", "sim_opportunity_windows"}
    for r in recs:
        assert r.layer is Layer.SIMULATED
        assert r.provenance.source_version == "seed=42;n_sims=8000"  # reproducible
        assert r.provenance.pipeline_version == "simulation/montecarlo"


def test_profile_and_embedding_are_derived():
    prof = profile_record({"archetype": "finisher", "pass_accuracy": 0.81},
                          Context(player_id="p1"), confidence=0.6)
    assert prof.layer is Layer.DERIVED and prof.kind == "player_profile"
    assert prof.provenance.pipeline_version == "profiling/dna"

    emb = embedding_record([0.1, 0.2, 0.3], Context(match_id="m1"))
    assert emb.layer is Layer.DERIVED and emb.value == [0.1, 0.2, 0.3]


def test_inferred_records_are_deterministic():
    preds = {"goal_next_10min": 0.19}
    a = [r.id for r in prediction_records(preds, MATCH, confidence=0.5)]
    b = [r.id for r in prediction_records(preds, MATCH, confidence=0.5)]
    assert a == b


def test_inferred_record_without_evidence_is_rejected():
    # The contract (make_record) refuses an inferred datum citing no evidence:
    # neither parents nor a pipeline version.
    with pytest.raises(IntegrityError):
        make_record("pred_x", 0.5, Layer.PROBABILISTIC, MATCH,
                    Provenance(source="engine"))


def test_lifted_records_never_pass_as_observed():
    recs = prediction_records({"goal_next_10min": 0.2}, MATCH)
    assert all(r.layer in {Layer.PROBABILISTIC} for r in recs)
    assert all(r.layer not in {Layer.OBSERVED, Layer.HISTORICAL} for r in recs)
