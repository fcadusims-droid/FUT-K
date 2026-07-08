"""Knowledge Base for Simulation — the leakage-free pre-match world state.

The simulator is handed knowledge as it was known before kick-off; nothing from
the future can enter, and simulated output stays independent until audited
(docs/design/DATASET_FUSION.md §Base de Conhecimento para Simulação).
"""

from __future__ import annotations

import pytest

from fie.fusiondata import Context, IntegrityError, Layer
from fie.dynamics import state_version
from fie.worldstate import (
    KnowledgeState,
    assemble_state,
    assert_no_future_leak,
    gate_incorporation,
    simulated_record,
)

P1 = Context(player_id="p1")
BRA = Context(team="Brazil")


def _pos(value, valid_from, collected_at=None):
    return state_version("position", value, P1, source="scout",
                         valid_from=valid_from, collected_at=collected_at)


# --------------------------------------------------------------------------- #
# Assembling the pre-match state, as of a cutoff
# --------------------------------------------------------------------------- #
def test_assemble_state_resolves_attributes_as_of_cutoff():
    records = [
        _pos("striker", "2019-01-01"),
        _pos("midfielder", "2022-07-01"),
        state_version("style", "high_press", BRA, source="analyst",
                      valid_from="2021-01-01"),
    ]
    # Simulating a 2020 match: the player is still a striker.
    state = assemble_state(records, as_of="2020-05-01")
    assert state.get("p1", "position") == "striker"
    # The team style is not yet known in 2020 (starts 2021).
    assert state.get("Brazil", "style") is None

    # Simulating a 2023 match: both are known.
    later = assemble_state(records, as_of="2023-05-01")
    assert later.get("p1", "position") == "midfielder"
    assert later.get("Brazil", "style") == "high_press"


def test_state_never_includes_the_future():
    records = [_pos("striker", "2019-01-01"), _pos("midfielder", "2022-07-01")]
    state = assemble_state(records, as_of="2020-01-01")
    # Only the striker version is present; the 2022 change is invisible.
    kinds = [r.value for r in state.records]
    assert kinds == ["striker"]
    assert_no_future_leak(state.records, "2020-01-01")     # provably clean


def test_collected_after_cutoff_is_a_leak():
    # A datum whose validity starts before the cutoff but that was *collected*
    # after it could not have been known — rejected.
    late = _pos("striker", "2019-01-01", collected_at="2021-01-01")
    with pytest.raises(IntegrityError):
        assert_no_future_leak([late], "2020-01-01")


def test_simulated_layer_cannot_seed_a_simulation():
    sim = simulated_record("proj_goals", 1.4, P1, pipeline_version="sim-v1",
                           parents=("evt1",))
    with pytest.raises(IntegrityError):
        assert_no_future_leak([sim], "2030-01-01")
    # ...and assemble_state simply ignores non-prior layers rather than leaking.
    state = assemble_state([sim, _pos("striker", "2019-01-01")], as_of="2020-01-01")
    assert state.get("p1", "position") == "striker"
    assert all(r.layer in {Layer.OBSERVED, Layer.HISTORICAL, Layer.YOUTH,
                           Layer.EXTERNAL, Layer.DERIVED} for r in state.records)


def test_derived_prior_knowledge_is_allowed():
    emb = state_version("embedding", [0.1, 0.2], P1, source="engine",
                        valid_from="2019-06-01", layer=Layer.DERIVED,
                        pipeline_version="emb-v1")
    state = assemble_state([emb], as_of="2020-01-01")
    assert state.get("p1", "embedding") == [0.1, 0.2]


# --------------------------------------------------------------------------- #
# Simulated output: independent, gated, provenance-tracked
# --------------------------------------------------------------------------- #
def test_simulated_record_is_independent_and_cites_evidence():
    state = assemble_state([_pos("striker", "2019-01-01")], as_of="2020-01-01")
    rec = simulated_record("win_prob", 0.62, Context(match_id="sim1"),
                           pipeline_version="poisson-v3", state=state,
                           produced_at="2026-01-01")
    assert rec.layer is Layer.SIMULATED
    # It cites the exact prior-knowledge records that seeded it.
    assert state.records[0].id in rec.provenance.parents
    assert rec.provenance.pipeline_version == "poisson-v3"


def test_gate_blocks_unaudited_and_admits_audited():
    sim = simulated_record("win_prob", 0.62, Context(match_id="sim1"),
                           pipeline_version="v3", parents=("evt1",))
    with pytest.raises(IntegrityError):
        gate_incorporation([sim], audited=False)
    admitted = gate_incorporation([sim], audited=True)
    # Still simulated (separation preserved), but the audit is recorded.
    assert admitted[0].layer is Layer.SIMULATED
    assert "audit:passed" in admitted[0].provenance.transformations


def test_gate_rejects_non_simulated_records():
    obs = _pos("striker", "2019-01-01")
    with pytest.raises(IntegrityError):
        gate_incorporation([obs], audited=True)


def test_knowledge_state_is_readonly_view():
    state = assemble_state([_pos("striker", "2019-01-01")], as_of="2020-01-01")
    assert isinstance(state, KnowledgeState)
    assert state.attributes("p1") == {"position": "striker"}
    assert state.get("p1", "missing", default="?") == "?"


def test_assemble_state_is_deterministic():
    records = [
        _pos("striker", "2019-01-01"),
        _pos("midfielder", "2022-07-01"),
        state_version("style", "press", BRA, source="a", valid_from="2021-01-01"),
    ]
    a = assemble_state(records, as_of="2023-01-01")
    b = assemble_state(list(records), as_of="2023-01-01")
    assert a.entities == b.entities
    assert [r.id for r in a.records] == [r.id for r in b.records]
