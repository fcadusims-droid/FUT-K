"""Persist the Dataset Fusion knowledge substrate (Phase B).

The engine half (``fie.fusiondata`` / ``fie.dynamics`` / ``fie.worldstate``) is
pure; this is its Application half: serialize a ``KnowledgeRecord`` into a
``knowledge_records`` row and back with **byte-faithful round-tripping** (the
rebuilt record recomputes the same id), then reuse the *validated* engine logic
for every read — as-of resolution, history, the leakage-free pre-match state and
the continuous audit — so the store never re-implements a rule the engine already
owns.

Append-only by contract: values are never overwritten. Re-storing the same id
updates only its temporal envelope (a supersede closing a prior version); a
correction is a brand-new id. Idempotent, so ingestion can re-run safely.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from fie.dynamics import append_version as dyn_append_version
from fie.dynamics import entity_id, history as dyn_history, state_as_of as dyn_state_as_of
from fie.fusiondata import (
    Context,
    KnowledgeRecord,
    Layer,
    Provenance,
    Temporal,
    audit_store,
    check_derivation_evidence,
    check_provenance,
    from_fused_fields,
    make_record,
)
from fie.fusion import fuse_match

from .models import KnowledgeRecordRow

_CONTEXT_FIELDS = (
    "competition", "season", "round", "match_id", "date", "home", "away",
    "team", "player_id", "event_id", "minute", "second",
)


# --------------------------------------------------------------------------- #
# Serialization — faithful both ways (the rebuilt record keeps the same id)
# --------------------------------------------------------------------------- #
def record_to_row(rec: KnowledgeRecord, stored_at: str) -> KnowledgeRecordRow:
    ctx = rec.context
    prov = rec.provenance
    return KnowledgeRecordRow(
        id=rec.id,
        logical_id=rec.logical_id,
        kind=rec.kind,
        layer=rec.layer.value,
        entity_id=entity_id(ctx),
        match_id=ctx.match_id,
        value_json=json.dumps(rec.value, sort_keys=True),
        context_json=json.dumps({f: getattr(ctx, f) for f in _CONTEXT_FIELDS},
                                sort_keys=True),
        provenance_json=json.dumps({
            "source": prov.source,
            "collected_at": prov.collected_at,
            "ingested_by": prov.ingested_by,
            "pipeline_version": prov.pipeline_version,
            "source_version": prov.source_version,
            "transformations": list(prov.transformations),
            "parents": list(prov.parents),
        }, sort_keys=True),
        valid_from=rec.temporal.valid_from,
        valid_to=rec.temporal.valid_to,
        superseded_by=rec.temporal.superseded_by,
        permanence=rec.temporal.permanence,
        confidence=rec.temporal.confidence,
        stored_at=stored_at,
    )


def row_to_record(row: KnowledgeRecordRow) -> KnowledgeRecord:
    ctx = Context(**json.loads(row.context_json))
    p = json.loads(row.provenance_json)
    prov = Provenance(
        source=p["source"], collected_at=p.get("collected_at"),
        ingested_by=p.get("ingested_by"), pipeline_version=p.get("pipeline_version"),
        source_version=p.get("source_version"),
        transformations=tuple(p.get("transformations") or ()),
        parents=tuple(p.get("parents") or ()),
    )
    temporal = Temporal(
        valid_from=row.valid_from, valid_to=row.valid_to,
        superseded_by=row.superseded_by, permanence=row.permanence,
        confidence=row.confidence,
    )
    return KnowledgeRecord(
        kind=row.kind, value=json.loads(row.value_json), layer=Layer(row.layer),
        context=ctx, provenance=prov, temporal=temporal,
    )


# --------------------------------------------------------------------------- #
# Write — idempotent, append-only, validated on the way in
# --------------------------------------------------------------------------- #
def store_records(session: Session, records) -> dict:
    """Upsert records by id. Values never change; only the temporal envelope may.

    Every record is validated (``check_provenance`` + ``check_derivation_evidence``)
    before it touches the DB — an untraceable or unsupported datum is rejected,
    not stored. Returns ``{"stored", "updated"}``.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stored = updated = 0
    for rec in records:
        check_provenance(rec)
        check_derivation_evidence(rec)
        existing = session.get(KnowledgeRecordRow, rec.id)
        if existing is None:
            session.add(record_to_row(rec, now))
            stored += 1
        else:
            # Same id => same value/context/source; only the temporal window and
            # provenance annotations can legitimately move (a supersede/audit).
            existing.valid_to = rec.temporal.valid_to
            existing.superseded_by = rec.temporal.superseded_by
            existing.permanence = rec.temporal.permanence
            existing.confidence = rec.temporal.confidence
            existing.provenance_json = record_to_row(rec, now).provenance_json
            updated += 1
    session.commit()
    return {"stored": stored, "updated": updated}


def load_versions(session: Session, kind: str, entity: str) -> list:
    rows = session.execute(
        select(KnowledgeRecordRow)
        .where(KnowledgeRecordRow.kind == kind,
               KnowledgeRecordRow.entity_id == entity)
    ).scalars().all()
    return [row_to_record(r) for r in rows]


def append_version(session: Session, new_record: KnowledgeRecord) -> dict:
    """Persist a new version, closing the prior one via the engine's rule.

    Delegates the timeline arithmetic to ``fie.dynamics.append_version`` (a
    permanent change closes the previous permanent live version; a temporary one
    coexists), then upserts the resulting set — so the DB supersede-chain is
    exactly what the pure engine would compute.
    """
    existing = load_versions(session, new_record.kind, entity_id(new_record.context))
    resulting = dyn_append_version(existing, new_record)
    return store_records(session, resulting)


# --------------------------------------------------------------------------- #
# Read — reuse the validated engine logic, never re-implement it
# --------------------------------------------------------------------------- #
def state_as_of(session: Session, kind: str, entity: str, at: str):
    rec = dyn_state_as_of(load_versions(session, kind, entity), at, kind, entity)
    return rec.to_dict() if rec is not None else None


def history(session: Session, kind: str, entity: str) -> list:
    return [r.to_dict() for r in dyn_history(load_versions(session, kind, entity),
                                             kind, entity)]


def _load_all(session: Session, layers=None) -> list:
    stmt = select(KnowledgeRecordRow)
    if layers is not None:
        stmt = stmt.where(KnowledgeRecordRow.layer.in_([l.value for l in layers]))
    return [row_to_record(r) for r in session.execute(stmt).scalars().all()]


def assemble_state(session: Session, as_of: str, entities=None) -> dict:
    """The leakage-free pre-match knowledge state, assembled from the store."""
    from fie.worldstate import PRIOR_LAYERS, assemble_state as ws_assemble

    records = _load_all(session, layers=PRIOR_LAYERS)
    state = ws_assemble(records, as_of, entities=entities)
    return {
        "as_of": state.as_of,
        "entities": state.entities,
        "n_records": len(state.records),
        "record_ids": [r.id for r in state.records],
    }


def audit(session: Session, known_players=None, known_matches=None) -> dict:
    """Continuous audit: replay the validators over the whole store."""
    return audit_store(_load_all(session), known_players=known_players,
                       known_matches=known_matches)


def knowledge_graph(session: Session, *, entity=None, relation=None,
                    as_of=None, node_type=None, limit=200) -> dict:
    """The Knowledge Graph over the whole store (or a node's neighbourhood).

    Builds the graph deterministically from every stored record's context. With
    ``entity`` (a node key like ``player:p1``) it returns that node's relations
    and neighbours (optionally filtered by ``relation`` and ``as_of``); otherwise
    the top ``limit`` edges of the whole graph, or the nodes of ``node_type``.
    """
    from fie.graph import build_graph

    graph = build_graph(_load_all(session))
    if entity:
        return {
            "entity": entity,
            "relations": [e.to_dict() for e in graph.relations(entity, as_of=as_of)],
            "neighbors": graph.neighbors(entity, relation=relation, as_of=as_of),
        }
    if node_type:
        return {"node_type": node_type,
                "nodes": [n.__dict__ | {"key": n.key}
                          for n in graph.nodes_of_type(node_type)]}
    return graph.to_dict(limit=limit)


def list_records(session: Session, kind=None, entity=None, layer=None,
                 match_id=None, current_only=False, limit=100) -> list:
    stmt = select(KnowledgeRecordRow)
    if kind:
        stmt = stmt.where(KnowledgeRecordRow.kind == kind)
    if entity:
        stmt = stmt.where(KnowledgeRecordRow.entity_id == entity)
    if layer:
        stmt = stmt.where(KnowledgeRecordRow.layer == layer)
    if match_id:
        stmt = stmt.where(KnowledgeRecordRow.match_id == match_id)
    if current_only:
        stmt = stmt.where(KnowledgeRecordRow.valid_to.is_(None),
                          KnowledgeRecordRow.superseded_by.is_(None))
    rows = session.execute(
        stmt.order_by(KnowledgeRecordRow.entity_id, KnowledgeRecordRow.kind,
                      KnowledgeRecordRow.valid_from).limit(limit)
    ).scalars().all()
    return [row_to_record(r).to_dict() for r in rows]


# --------------------------------------------------------------------------- #
# Migration bridge — fused match facts become OBSERVED knowledge records
# --------------------------------------------------------------------------- #
def store_fused_as_knowledge(session: Session, league: str, resolved: list,
                             fields: dict, priors: dict | None = None) -> dict:
    """Write every 2+-source fused fixture into the knowledge store.

    The Phase-B migration: the same reconciliation ``store_fused`` persists as a
    ``FusedMatchRecord`` is *also* lifted into the substrate via
    ``from_fused_fields`` — each fused field an OBSERVED record keyed to the
    fixture, with its winning sources, confidence and recorded dissent intact.
    Idempotent by content-addressed id.
    """
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_records = []
    for fixture in resolved:
        if len(fixture["records"]) < 2:
            continue
        date, home, away = fixture["key"]
        unified = fuse_match(fixture["records"], fields, priors)
        context = Context(date=date, home=home, away=away,
                          match_id=f"{date}|{home}|{away}", competition=league)
        provenance = Provenance(source="fusion", collected_at=ingested_at,
                                ingested_by="store_fused_as_knowledge",
                                pipeline_version="fuse/1.1")
        all_records.extend(from_fused_fields(unified, context, provenance))
    result = store_records(session, all_records)
    result["fixtures"] = sum(1 for f in resolved if len(f["records"]) >= 2)
    return result


def store_simulation(session: Session, sim_records, *, audited: bool) -> dict:
    """Admit simulation output into the store — only through the audit gate.

    Simulated data stays independent until validated: ``gate_incorporation`` raises
    unless ``audited`` is True, and even then the records keep the ``SIMULATED``
    layer (never mistaken for observed fact) with the audit stamped into their
    provenance. Then they persist like any other knowledge.
    """
    from fie.worldstate import gate_incorporation

    admitted = gate_incorporation(sim_records, audited=audited)
    return store_records(session, admitted)


# --------------------------------------------------------------------------- #
# Phase C — capture the engine's own inferred outputs into the store
# --------------------------------------------------------------------------- #
def capture_panel(session: Session, panel: dict) -> dict:
    """Persist a panel's predictions as PROBABILISTIC records for that minute.

    The panel already carries its confidence; each predicted target lands as an
    inferred record citing the Poisson model, pinned to (match, minute).
    """
    from fie.knowledgemap import prediction_records

    context = Context(match_id=panel.get("match_id"), minute=panel.get("minute"))
    records = prediction_records(
        panel.get("predictions", {}), context,
        confidence=panel.get("confidence"),
    )
    result = store_records(session, records)
    result["kind"] = "predictions"
    return result


def capture_simulation(session: Session, match_id: str, minute: float,
                       sim: dict) -> dict:
    """Persist a Future Simulation result as gated SIMULATED records.

    Goes through the same audit gate as any incorporated simulation
    (``audited=True`` — this is the engine's own deterministic, seeded output,
    captured deliberately), so the separation from observed fact is preserved.
    """
    from fie.knowledgemap import simulation_records

    context = Context(match_id=match_id, minute=minute)
    records = simulation_records(sim, context)
    result = store_simulation(session, records, audited=True)
    result["kind"] = "simulation"
    return result


# --------------------------------------------------------------------------- #
# Phase D — deterministic contextual data + behavioral indices
# --------------------------------------------------------------------------- #
def capture_context(session: Session, match_id: str) -> dict:
    """Persist a match's deterministic context (venue, rest, congestion).

    Venue is a fact; rest days and fixture congestion are derived from the
    calendar already in the DB — no external feed. Stored as OBSERVED contextual
    records (one per team), plus the competition's strength (mean goals/match) as
    a DERIVED aggregate citing its evidence.
    """
    from fie.context import competition_strength, match_context
    from fie.knowledgemap import derived_record

    from .models import Match

    m = session.get(Match, match_id)
    if m is None:
        return {"stored": 0, "updated": 0, "note": "match not found"}

    def _team_dates(team):
        rows = session.execute(
            select(Match).where((Match.home_team == team) | (Match.away_team == team))
        ).scalars().all()
        return [r.match_date for r in rows if r.match_date]

    records = []
    for team, is_home in ((m.home_team, True), (m.away_team, False)):
        if not team:
            continue
        facts = match_context(team, is_home, _team_dates(team), m.match_date or "")
        records.append(make_record(
            kind="team_context",
            value={k: facts[k] for k in ("venue", "rest_days", "fixture_congestion")},
            layer=Layer.OBSERVED,
            context=Context(match_id=match_id, team=team, date=m.match_date,
                            competition=m.competition),
            provenance=Provenance(source="calendar", ingested_by="capture_context"),
        ))
    result = store_records(session, records)

    # Competition strength — a derived aggregate over the competition's fixtures.
    if m.competition:
        comp_rows = session.execute(
            select(Match).where(Match.competition == m.competition)
        ).scalars().all()
        gpm = [
            (r.home_goals_final + r.away_goals_final)
            for r in comp_rows
            if r.home_goals_final is not None and r.away_goals_final is not None
        ]
        strength = competition_strength(gpm)
        if strength is not None:
            store_records(session, [derived_record(
                "competition_strength", strength,
                Context(competition=m.competition),
                pipeline_version="context/competition_strength")])
            result["competition_strength"] = strength
    result["kind"] = "context"
    return result


def capture_behavior(session: Session, player_id: str) -> dict:
    """Persist a player's behavioral indices as one DERIVED record.

    Reads the player's DNA profile (for the share-based indices) and their events
    (for discipline and the involvement curve); indices the data cannot support
    abstain honestly. Nothing is fabricated.
    """
    from fie.behavior import behavioral_profile
    from fie.knowledgemap import behavior_record
    from fie.events import Event

    from .models import MatchEvent, PlayerProfile

    row = session.get(PlayerProfile, player_id)
    if row is None:
        return {"stored": 0, "updated": 0, "note": "player profile not found"}
    profile = {
        "player_id": player_id,
        "pass_accuracy": row.pass_accuracy,
        "turnover_rate": row.turnover_rate,
        "actions": row.actions,
        "confidence": row.confidence,
    }
    ev_rows = session.execute(
        select(MatchEvent).where(MatchEvent.player_id == player_id)
    ).scalars().all()
    events = [Event(match_id=e.match_id, minute=e.minute, team=e.team, type=e.type,
                    player_id=e.player_id) for e in ev_rows]
    indices = behavioral_profile(profile, events=events)
    result = store_records(session, [behavior_record(
        indices, Context(player_id=player_id), confidence=row.confidence)])
    result["kind"] = "behavior"
    result["indices"] = indices
    return result
