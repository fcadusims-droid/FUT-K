"""Dataset Fusion persistence (Phase B): the knowledge store + /knowledge API.

Round-trips are byte-faithful (a rebuilt record recomputes the same id), the
supersede-chain and as-of resolution reuse the validated engine logic, and the
audit catches contradictions before they spread.
"""

from __future__ import annotations

import pytest

from fie.fusion import resolve_matches
from fie.fusiondata import Context, IntegrityError, Layer, make_record, Provenance
from fie.dynamics import state_version

from app.knowledgestore import (
    append_version,
    audit,
    history,
    list_records,
    row_to_record,
    state_as_of,
    store_fused_as_knowledge,
    store_records,
    store_simulation,
)
from app.models import KnowledgeRecordRow

P1 = Context(player_id="p1")


def _pos(value, valid_from, **kw):
    return state_version("position", value, P1, source="scout",
                         valid_from=valid_from, **kw)


# --------------------------------------------------------------------------- #
# Serialization round-trip + idempotence
# --------------------------------------------------------------------------- #
def test_store_round_trip_preserves_id_and_content(db_session):
    rec = _pos("striker", "2019-01-01", confidence=0.8)
    assert store_records(db_session, [rec]) == {"stored": 1, "updated": 0}

    row = db_session.get(KnowledgeRecordRow, rec.id)
    rebuilt = row_to_record(row)
    # Faithful: the rebuilt record recomputes the same content-addressed id.
    assert rebuilt.id == rec.id
    assert rebuilt.value == "striker"
    assert rebuilt.temporal.confidence == 0.8
    assert rebuilt.provenance.source == "scout"

    # Idempotent: re-storing the same id updates in place, never duplicates.
    assert store_records(db_session, [rec]) == {"stored": 0, "updated": 1}
    assert db_session.query(KnowledgeRecordRow).count() == 1


def test_store_rejects_untraceable_record(db_session):
    # A record with no source cannot be built via make_record; store_records
    # re-checks provenance defensively, so construct directly to prove the guard.
    from fie.fusiondata import KnowledgeRecord, Temporal
    orphan = KnowledgeRecord(kind="x", value=1, layer=Layer.OBSERVED,
                             context=P1, provenance=Provenance(source=""),
                             temporal=Temporal())
    with pytest.raises(IntegrityError):
        store_records(db_session, [orphan])


# --------------------------------------------------------------------------- #
# Append-only supersede chain, persisted
# --------------------------------------------------------------------------- #
def test_append_version_closes_prior_in_db(db_session):
    striker = _pos("striker", "2019-01-01")
    store_records(db_session, [striker])
    midfielder = _pos("midfielder", "2022-07-01")
    append_version(db_session, midfielder)

    # Both versions live in the store; the old one is closed and linked forward.
    rows = {r.value_json: r for r in db_session.query(KnowledgeRecordRow).all()}
    old = db_session.get(KnowledgeRecordRow, striker.id)
    assert old.valid_to == "2022-07-01"
    assert old.superseded_by == midfielder.id
    new = db_session.get(KnowledgeRecordRow, midfielder.id)
    assert new.valid_to is None and new.superseded_by is None
    assert len(rows) == 2


def test_history_and_as_of_from_store(db_session):
    for v, d in [("striker", "2019-01-01"), ("winger", "2020-08-01"),
                 ("midfielder", "2022-07-01")]:
        append_version(db_session, _pos(v, d))

    values = [h["value"] for h in history(db_session, "position", "p1")]
    assert values == ["striker", "winger", "midfielder"]        # nothing lost

    assert state_as_of(db_session, "position", "p1", "2020-05-01")["value"] == "striker"
    assert state_as_of(db_session, "position", "p1", "2023-01-01")["value"] == "midfielder"
    assert state_as_of(db_session, "position", "p1", "2000-01-01") is None


def test_temporary_state_persists_and_reverts(db_session):
    append_version(db_session, _pos("striker", "2019-01-01"))
    from fie.fusiondata import TEMPORARY
    append_version(db_session, _pos("false_nine", "2023-03-10",
                                    permanence=TEMPORARY, valid_to="2023-03-11"))
    assert state_as_of(db_session, "position", "p1", "2023-03-10")["value"] == "false_nine"
    assert state_as_of(db_session, "position", "p1", "2023-04-01")["value"] == "striker"


# --------------------------------------------------------------------------- #
# Continuous audit catches contradictions
# --------------------------------------------------------------------------- #
def test_audit_ok_and_detects_player_on_two_teams(db_session):
    ev = lambda team: make_record(  # noqa: E731
        "pass", 1, Layer.OBSERVED,
        Context(match_id="m1", minute=10.0, player_id="p9", team=team),
        Provenance(source="statsbomb"))
    store_records(db_session, [ev("HOME")])
    assert audit(db_session)["ok"] is True

    store_records(db_session, [ev("AWAY")])       # same player, two teams, one match
    with pytest.raises(IntegrityError):
        audit(db_session)


# --------------------------------------------------------------------------- #
# Migration: fused match facts -> OBSERVED knowledge records
# --------------------------------------------------------------------------- #
def test_store_fused_as_knowledge_preserves_dissent(db_session):
    sources = {
        "alpha": [{"date": "2024-04-14", "home": "Leverkusen", "away": "Werder Bremen",
                   "home_goals": 5, "corners_home": 7}],
        "beta": [{"date": "2024-04-14", "home": "Bayer 04 Leverkusen",
                  "away": "SV Werder Bremen", "home_goals": 5, "corners_home": 8}],
    }
    resolved = resolve_matches(sources)
    fields = {"home_goals": 0, "corners_home": 0}
    result = store_fused_as_knowledge(db_session, "Bundesliga 2023/24", resolved,
                                      fields, priors={"alpha": 0.95, "beta": 0.9})
    assert result["fixtures"] == 1 and result["stored"] == 2

    recs = list_records(db_session, layer="observed")
    corners = next(r for r in recs if r["kind"] == "corners_home")
    assert corners["value"]["value"] == 7                     # alpha wins by prior
    assert corners["value"]["dissent"] == {"beta": 8}         # honesty preserved
    assert corners["layer"] == "observed"
    assert corners["provenance"]["from_which_source"] == "fusion"


# --------------------------------------------------------------------------- #
# Simulated output: gated before it can enter the store
# --------------------------------------------------------------------------- #
def test_store_simulation_requires_audit(db_session):
    from fie.worldstate import simulated_record

    sim = simulated_record("win_prob", 0.6, Context(match_id="m1"),
                           pipeline_version="v3", parents=("evt1",))
    with pytest.raises(IntegrityError):
        store_simulation(db_session, [sim], audited=False)
    assert store_simulation(db_session, [sim], audited=True) == {"stored": 1, "updated": 0}
    row = db_session.get(KnowledgeRecordRow, sim.id)
    assert row.layer == "simulated"                            # separation preserved


# --------------------------------------------------------------------------- #
# The /knowledge/* API
# --------------------------------------------------------------------------- #
def test_knowledge_endpoints(client, db_session):
    for v, d in [("striker", "2019-01-01"), ("midfielder", "2022-07-01")]:
        append_version(db_session, _pos(v, d))

    recs = client.get("/knowledge/records?entity=p1").json()
    assert len(recs) == 2

    hist = client.get("/knowledge/history?kind=position&entity=p1").json()
    assert [h["value"] for h in hist] == ["striker", "midfielder"]

    asof = client.get("/knowledge/as-of?kind=position&entity=p1&at=2020-06-01").json()
    assert asof["value"] == "striker"
    assert client.get("/knowledge/as-of?kind=position&entity=p1&at=1999-01-01").status_code == 404

    audit_body = client.get("/knowledge/audit").json()
    assert audit_body["ok"] is True and audit_body["records"] == 2
