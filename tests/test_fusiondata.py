"""Dataset Fusion substrate — the integrity & isolation contract.

Every datum carries its context, provenance, temporal validity and layer, and
the defensive validators prevent the combinations the vision forbids
(docs/design/DATASET_FUSION.md). Deterministic throughout.
"""

from __future__ import annotations

import pytest

from fie.fusiondata import (
    Context,
    IntegrityError,
    KnowledgeRecord,
    Layer,
    Provenance,
    Temporal,
    assert_integrity,
    assert_no_fact_inference_mix,
    assert_player_single_team,
    assert_single_match,
    assert_single_season,
    check_aggregate_consistency,
    check_chronology,
    check_derivation_evidence,
    check_provenance,
    check_referential_integrity,
    from_fused_fields,
    logical_key,
    make_record,
    record_id,
    safe_to_fuse,
)


# --------------------------------------------------------------------------- #
# Identity: deterministic, content-addressed, version-stable
# --------------------------------------------------------------------------- #
def _obs(kind="match_goals", value=3, source="statsbomb", **ctx):
    return make_record(
        kind=kind, value=value, layer=Layer.OBSERVED,
        context=Context(**ctx),
        provenance=Provenance(source=source, collected_at="2024-01-01T00:00:00"),
    )


def test_record_id_is_deterministic_and_content_addressed():
    a = _obs(match_id="m1", value=3)
    b = _obs(match_id="m1", value=3)
    assert a.id == b.id                      # same inputs -> same id
    assert _obs(match_id="m1", value=4).id != a.id   # value change -> new id
    assert _obs(match_id="m2", value=3).id != a.id   # context change -> new id


def test_logical_key_is_stable_across_versions():
    v1 = _obs(match_id="m1", value=3)
    # A correction: same thing, new value/time -> same logical id, different id.
    v2 = make_record(
        kind="match_goals", value=4, layer=Layer.OBSERVED,
        context=Context(match_id="m1"),
        provenance=Provenance(source="statsbomb", collected_at="2024-02-01T00:00:00"),
    )
    assert v1.logical_id == v2.logical_id
    assert v1.id != v2.id
    assert v1.logical_id == logical_key(Layer.OBSERVED, "match_goals",
                                        Context(match_id="m1"), "statsbomb")


def test_record_id_helper_matches_property():
    r = _obs(match_id="m1", value=3)
    assert r.id == record_id(Layer.OBSERVED, "match_goals", Context(match_id="m1"),
                             "statsbomb", 3, "2024-01-01T00:00:00")


# --------------------------------------------------------------------------- #
# Context is never stripped; enrichment cannot overwrite
# --------------------------------------------------------------------------- #
def test_context_enrich_fills_but_never_overwrites():
    ctx = Context(match_id="m1", team=None)
    enriched = ctx.enrich(team="HOME")
    assert enriched.team == "HOME" and enriched.match_id == "m1"
    # Restating an equal value is fine; changing an existing one is forbidden.
    assert enriched.enrich(team="HOME").team == "HOME"
    with pytest.raises(IntegrityError):
        enriched.enrich(team="AWAY")


# --------------------------------------------------------------------------- #
# Provenance: the six questions; additive transformation chain
# --------------------------------------------------------------------------- #
def test_provenance_answers_six_questions():
    r = _obs(match_id="m1")
    q = r.provenance.questions()
    assert set(q) == {"from_which_source", "collected_when", "ingested_by",
                      "pipeline_version", "transformations", "derived_from"}
    assert q["from_which_source"] == "statsbomb"


def test_provenance_transformations_are_additive():
    p = Provenance(source="s").with_transformation("normalize").with_transformation(
        "fuse", "parent1")
    assert p.transformations == ("normalize", "fuse")
    assert p.parents == ("parent1",)


def test_record_without_source_is_rejected():
    with pytest.raises(IntegrityError):
        make_record("k", 1, Layer.OBSERVED, Context(), Provenance(source=""))


# --------------------------------------------------------------------------- #
# Temporal: nothing is permanent; corrections append, never overwrite
# --------------------------------------------------------------------------- #
def test_temporal_current_and_supersede():
    t = Temporal(valid_from="2024-01-01")
    assert t.is_current()
    closed = t.close(valid_to="2024-02-01", superseded_by="newid")
    assert not closed.is_current()
    assert closed.valid_to == "2024-02-01" and closed.superseded_by == "newid"


# --------------------------------------------------------------------------- #
# Derivation evidence: inferred data must cite what produced it
# --------------------------------------------------------------------------- #
def test_inferred_record_must_cite_evidence():
    with pytest.raises(IntegrityError):
        make_record("win_prob", 0.7, Layer.PROBABILISTIC, Context(match_id="m1"),
                    Provenance(source="engine"))          # no parents, no pipeline
    # Citing a pipeline version is enough...
    ok_pipeline = make_record(
        "win_prob", 0.7, Layer.PROBABILISTIC, Context(match_id="m1"),
        Provenance(source="engine", pipeline_version="poisson-v3"))
    check_derivation_evidence(ok_pipeline)
    # ...and so is citing parent records.
    ok_parents = make_record(
        "sim_outcome", {"home_win": 0.5}, Layer.SIMULATED, Context(match_id="m1"),
        Provenance(source="engine", parents=("evt1", "evt2")))
    check_derivation_evidence(ok_parents)


def test_factual_record_needs_no_evidence_link():
    check_derivation_evidence(_obs(match_id="m1"))         # does not raise
    check_provenance(_obs(match_id="m1"))


# --------------------------------------------------------------------------- #
# Isolation: matches, seasons, layers, fact/inference
# --------------------------------------------------------------------------- #
def test_single_match_isolation():
    same = [_obs(match_id="m1", kind="a"), _obs(match_id="m1", kind="b")]
    assert_single_match(same)                              # ok
    with pytest.raises(IntegrityError):
        assert_single_match([_obs(match_id="m1"), _obs(match_id="m2")])


def test_single_season_isolation():
    with pytest.raises(IntegrityError):
        assert_single_season([
            _obs(competition="LaLiga", season="2015/16"),
            _obs(competition="LaLiga", season="2016/17"),
        ])


def test_fact_inference_never_mix():
    fact = _obs(match_id="m1")
    inferred = make_record("win_prob", 0.6, Layer.PROBABILISTIC, Context(match_id="m1"),
                           Provenance(source="engine", pipeline_version="v1"))
    with pytest.raises(IntegrityError):
        assert_no_fact_inference_mix([fact, inferred])


def test_player_cannot_be_on_two_teams_in_one_match():
    ok = [
        _obs(kind="pass", match_id="m1", player_id="p1", team="HOME"),
        _obs(kind="shot", match_id="m1", player_id="p1", team="HOME"),
    ]
    assert_player_single_team(ok)
    # Same player switching clubs across DIFFERENT matches is legitimate.
    assert_player_single_team([
        _obs(match_id="m1", player_id="p1", team="HOME"),
        _obs(match_id="m2", player_id="p1", team="AWAY"),
    ])
    with pytest.raises(IntegrityError):
        assert_player_single_team([
            _obs(match_id="m1", player_id="p1", team="HOME"),
            _obs(match_id="m1", player_id="p1", team="AWAY"),
        ])


# --------------------------------------------------------------------------- #
# Referential integrity
# --------------------------------------------------------------------------- #
def test_event_requires_a_match():
    # Anchored in time (minute set) but no match -> structural violation.
    orphan = _obs(kind="shot", minute=42.0)
    with pytest.raises(IntegrityError):
        check_referential_integrity([orphan])


def test_unknown_player_and_match_are_rejected_when_reference_given():
    rec = _obs(kind="pass", match_id="m1", minute=10.0, player_id="p9", team="HOME")
    with pytest.raises(IntegrityError):
        check_referential_integrity([rec], known_players={"p1", "p2"})
    with pytest.raises(IntegrityError):
        check_referential_integrity([rec], known_matches={"m2"})
    # Valid references pass.
    check_referential_integrity([rec], known_players={"p9"}, known_matches={"m1"})


# --------------------------------------------------------------------------- #
# Chronology & aggregate consistency
# --------------------------------------------------------------------------- #
def test_chronology_must_not_run_backwards():
    ordered = [_obs(kind="a", match_id="m1", minute=10.0),
               _obs(kind="b", match_id="m1", minute=25.0)]
    check_chronology(ordered)
    with pytest.raises(IntegrityError):
        check_chronology([_obs(kind="a", match_id="m1", minute=25.0),
                          _obs(kind="b", match_id="m1", minute=10.0)])


def test_aggregate_must_match_underlying_events():
    corners = [_obs(kind="corner", match_id="m1", minute=float(m), team="HOME")
               for m in (12, 40, 77)]
    agg = _obs(kind="corners_home", match_id="m1", value=3, team="HOME")
    check_aggregate_consistency(agg, corners)
    bad = _obs(kind="corners_home", match_id="m1", value=5, team="HOME")
    with pytest.raises(IntegrityError):
        check_aggregate_consistency(bad, corners)


# --------------------------------------------------------------------------- #
# safe_to_fuse: the precondition guard for fusion
# --------------------------------------------------------------------------- #
def test_safe_to_fuse_requires_same_target_multiple_sources_one_layer():
    ctx = Context(match_id="m1", date="2024-01-01", home="a", away="b")
    sb = make_record("home_goals", 3, Layer.OBSERVED, ctx,
                     Provenance(source="statsbomb"))
    fd = make_record("home_goals", 3, Layer.OBSERVED, ctx,
                     Provenance(source="football_data"))
    safe_to_fuse([sb, fd])                                 # ok: same target, 2 sources
    # Different target -> refuse.
    other = make_record("away_goals", 2, Layer.OBSERVED, ctx,
                        Provenance(source="football_data"))
    with pytest.raises(IntegrityError):
        safe_to_fuse([sb, other])
    # Single source -> nothing to cross-check.
    with pytest.raises(IntegrityError):
        safe_to_fuse([sb, make_record("home_goals", 3, Layer.OBSERVED, ctx,
                                      Provenance(source="statsbomb"))])


# --------------------------------------------------------------------------- #
# Bridge from the existing fie.fusion output
# --------------------------------------------------------------------------- #
def test_from_fused_fields_lifts_fusion_output_with_provenance():
    from fie.fusion import fuse_match, resolve_matches

    sources = {
        "sb": [{"date": "2023-08-19", "home": "Leverkusen", "away": "Leipzig",
                "home_goals": 3, "corners": 7}],
        "fd": [{"date": "2023-08-19", "home": "Bayer 04 Leverkusen", "away": "RB Leipzig",
                "home_goals": 3, "corners": 8}],
    }
    resolved = resolve_matches(sources)
    fused = fuse_match(resolved[0]["records"], {"home_goals": 0, "corners": 0},
                       priors={"sb": 0.95, "fd": 0.9})
    ctx = Context(match_id="m1", date="2023-08-19",
                  home="bayer leverkusen", away="leipzig")
    records = from_fused_fields(fused, ctx, Provenance(source="fusion",
                                                       pipeline_version="fuse-v1"))
    kinds = {r.kind for r in records}
    assert kinds == {"home_goals", "corners"}              # no _conflicts/_sources
    goals = next(r for r in records if r.kind == "home_goals")
    assert goals.layer is Layer.OBSERVED
    assert goals.value["value"] == 3 and goals.value["agreed"] is True
    corners = next(r for r in records if r.kind == "corners")
    assert corners.value["dissent"] == {"fd": 8}           # honesty preserved
    # The transformation chain records the fuse step.
    assert "fuse:corners" in corners.provenance.transformations


# --------------------------------------------------------------------------- #
# assert_integrity: the always-on umbrella + full determinism
# --------------------------------------------------------------------------- #
def test_assert_integrity_runs_structural_checks():
    good = [
        _obs(kind="pass", match_id="m1", minute=10.0, player_id="p1", team="HOME"),
        _obs(kind="shot", match_id="m1", minute=30.0, player_id="p1", team="HOME"),
    ]
    assert_integrity(good, single_match=True,
                     known_players={"p1"}, known_matches={"m1"})
    with pytest.raises(IntegrityError):
        assert_integrity(good + [_obs(kind="x", match_id="m2", minute=1.0)],
                         single_match=True)


def test_to_dict_is_json_ready_and_deterministic():
    import json

    r = _obs(match_id="m1", value=3, player_id="p1", team="HOME")
    d = r.to_dict()
    assert json.dumps(d, sort_keys=True) == json.dumps(r.to_dict(), sort_keys=True)
    assert d["layer"] == "observed" and d["provenance"]["from_which_source"] == "statsbomb"
    assert "second" not in d["context"]                    # None fields dropped
