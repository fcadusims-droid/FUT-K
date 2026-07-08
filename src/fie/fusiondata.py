"""Dataset Fusion — the unified knowledge substrate (Inference).

``fie.fusion`` reconciles *one fact* (a match's score, corners, cards) across
providers. This module is the layer beneath that ambition: the **contract every
datum obeys** so that the Dataset Fusion can grow from match-reconciliation into
the unified knowledge base described in ``docs/design/DATASET_FUSION.md`` —
structured facts, youth trajectories, contextual, temporal, derived,
probabilistic, behavioral and simulated knowledge — without ever mixing what
must stay apart.

The founding rule of that vision is *integrity by isolation*: a pass only means
something inside the match it happened in; a simulated goal is never an observed
one; a derived index is worthless without a link back to its evidence. So every
datum here is a :class:`KnowledgeRecord` that permanently carries four things it
can never shed:

* a :class:`Context` — *where* it lives (competition, season, match, player,
  minute…). Transformations may enrich it; nothing may strip it.
* a :class:`Provenance` — *where it came from* and *how it got here* (the six
  provenance questions). No datum exists without it.
* a :class:`Temporal` — *when it is true*. Nothing is permanent; a correction
  appends a new version and closes the old one — history is never overwritten.
* a :class:`Layer` — *what kind* of knowledge it is (observed vs derived vs
  probabilistic vs simulated…), the domain separation that keeps inference from
  contaminating fact.

Everything is a pure function of its inputs: same records, same ids, same
verdicts — today and in six months. Standard-library only (Core/Inference
discipline), and the integrity checks *raise* rather than warn, because the
vision demands that bad combinations be prevented by architecture, not merely
flagged by tests.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Optional


class IntegrityError(Exception):
    """A datum, or a combination of data, violated the isolation contract."""


class Layer(str, Enum):
    """The knowledge domain a datum belongs to (§Separação por Camadas).

    The split exists so inference can never be confused with observation. The
    four factual layers record what was seen; the four inferred layers record
    what a model produced from it.
    """

    OBSERVED = "observed"          # facts seen in a match (events, stats)
    HISTORICAL = "historical"      # past facts (results, standings, transfers)
    YOUTH = "youth"                # base-category facts (Sub-13..Sub-23)
    EXTERNAL = "external"          # facts from an outside provider (e.g. bios)
    DERIVED = "derived"            # computed from facts (embeddings, profiles)
    PROBABILISTIC = "probabilistic"  # model estimates (win prob, potential…)
    SIMULATED = "simulated"        # simulation engine output (futures)
    EXPERIMENTAL = "experimental"  # not yet promoted; kept apart on purpose


FACTUAL_LAYERS = frozenset(
    {Layer.OBSERVED, Layer.HISTORICAL, Layer.YOUTH, Layer.EXTERNAL}
)
INFERRED_LAYERS = frozenset(
    {Layer.DERIVED, Layer.PROBABILISTIC, Layer.SIMULATED, Layer.EXPERIMENTAL}
)


# --------------------------------------------------------------------------- #
# Context — the immutable identity of a datum (§Princípios de Isolamento)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Context:
    """Where a datum lives in the football ecosystem — never stripped.

    Every field that localizes the datum. Optional fields stay ``None`` when they
    do not apply (a club-level fact has no minute), but whatever context exists
    travels with the datum for its whole life. Frozen, so a transformation can
    only produce a *new* context (via :meth:`enrich`), never mutate this one.
    """

    competition: Optional[str] = None
    season: Optional[str] = None
    round: Optional[str] = None
    match_id: Optional[str] = None
    date: Optional[str] = None
    home: Optional[str] = None
    away: Optional[str] = None
    team: Optional[str] = None
    player_id: Optional[str] = None
    event_id: Optional[str] = None
    minute: Optional[float] = None
    second: Optional[float] = None

    def key(self) -> tuple:
        """A hashable, order-stable tuple of the full context."""
        return (
            self.competition, self.season, self.round, self.match_id, self.date,
            self.home, self.away, self.team, self.player_id, self.event_id,
            self.minute, self.second,
        )

    def enrich(self, **fields) -> "Context":
        """Return a context with extra fields set — refusing to strip any.

        Enrichment may *fill* a ``None`` field or restate an equal value; it may
        never overwrite an existing field with a different one (that would be
        losing the datum's origin, which the isolation contract forbids).
        """
        for name, value in fields.items():
            current = getattr(self, name)
            if current is not None and value is not None and current != value:
                raise IntegrityError(
                    f"context.{name} is already {current!r}; refusing to "
                    f"overwrite with {value!r} (context is never rewritten)"
                )
        return replace(self, **fields)


# --------------------------------------------------------------------------- #
# Provenance — the six questions every datum must answer (§Proveniência)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Provenance:
    """Where a datum came from and how it got here.

    Answers, for every datum: *from which source?* *collected when?* *ingested
    by which process?* *processed by which pipeline version?* *through which
    transformations?* *derived from which records?* A datum without a source is
    rejected by :func:`check_provenance`.
    """

    source: str
    collected_at: Optional[str] = None      # when it was collected (ISO)
    ingested_by: Optional[str] = None        # the process that ingested it
    pipeline_version: Optional[str] = None   # the pipeline that produced it
    source_version: Optional[str] = None     # the source's own version/snapshot
    transformations: tuple = ()              # ordered names of applied steps
    parents: tuple = ()                      # ids of records this derives from

    def with_transformation(self, name: str, *parents: str) -> "Provenance":
        """Append a transformation step (and any new parent record ids).

        Provenance is additive — a step is recorded, never erased — so the full
        transformation chain is always reconstructable from the datum itself.
        """
        new_parents = self.parents + tuple(p for p in parents if p not in self.parents)
        return replace(
            self,
            transformations=self.transformations + (name,),
            parents=new_parents,
        )

    def questions(self) -> dict:
        """The six provenance answers, as an auditable dict."""
        return {
            "from_which_source": self.source,
            "collected_when": self.collected_at,
            "ingested_by": self.ingested_by,
            "pipeline_version": self.pipeline_version,
            "transformations": list(self.transformations),
            "derived_from": list(self.parents),
        }


# --------------------------------------------------------------------------- #
# Temporal — validity in time (§Dados Temporais: nothing is permanent)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Temporal:
    """When a datum is true, and whether a newer version has replaced it.

    ``valid_from``/``valid_to`` bound the datum's truth window; ``superseded_by``
    links to the record that replaced it. A live datum has ``valid_to is None``
    and no successor. Correcting a datum never overwrites it — it closes this
    version and appends a new one (:meth:`superseded_by`).
    """

    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    superseded_by: Optional[str] = None

    def is_current(self) -> bool:
        """True while this version is still the live one (open, un-replaced)."""
        return self.valid_to is None and self.superseded_by is None

    def close(self, valid_to: str, superseded_by: Optional[str] = None) -> "Temporal":
        """Return a closed version — the append-only way to correct a datum."""
        return replace(self, valid_to=valid_to, superseded_by=superseded_by)


# --------------------------------------------------------------------------- #
# The unified record + its deterministic global identity
# --------------------------------------------------------------------------- #
def _canonical(value: Any) -> str:
    """A deterministic string for any JSON-friendly value (sorted keys)."""
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def logical_key(layer: Layer, kind: str, context: Context, source: str) -> str:
    """Stable identity of *what a datum is about*, across its versions.

    Two versions of the same fact (an original and a later correction) share a
    logical key but differ in :func:`record_id`. This is the anchor a
    supersede-chain hangs on — deterministic and source-scoped, so one
    provider's view is never silently merged into another's.
    """
    payload = _canonical(
        {"layer": layer.value, "kind": kind, "context": context.key(), "source": source}
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def record_id(
    layer: Layer, kind: str, context: Context, source: str,
    value: Any, collected_at: Optional[str],
) -> str:
    """A content-addressed global id for one *version* of a datum.

    Includes the value and collection time, so any change mints a new id while
    the same inputs always reproduce the same id — the byte-reproducibility the
    rest of FUT-K is built on, applied to knowledge itself.
    """
    payload = _canonical({
        "layer": layer.value, "kind": kind, "context": context.key(),
        "source": source, "value": value, "collected_at": collected_at,
    })
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class KnowledgeRecord:
    """One datum in the Dataset Fusion, carrying its full contract.

    ``kind`` names the datum ("match_goals", "player_bio", "sim_outcome"…);
    ``value`` is its JSON-serializable payload. The datum drags its
    :class:`Context`, :class:`Provenance`, :class:`Temporal` and :class:`Layer`
    with it forever, and exposes a deterministic global :attr:`id`.
    """

    kind: str
    value: Any
    layer: Layer
    context: Context
    provenance: Provenance
    temporal: Temporal = field(default_factory=Temporal)

    @property
    def id(self) -> str:
        """Deterministic version id (content-addressed)."""
        return record_id(
            self.layer, self.kind, self.context,
            self.provenance.source, self.value, self.provenance.collected_at,
        )

    @property
    def logical_id(self) -> str:
        """Deterministic identity of what this datum is about (version-stable)."""
        return logical_key(self.layer, self.kind, self.context, self.provenance.source)

    def to_dict(self) -> dict:
        """A flat, auditable, JSON-ready view (persistence-ready)."""
        return {
            "id": self.id,
            "logical_id": self.logical_id,
            "kind": self.kind,
            "layer": self.layer.value,
            "value": self.value,
            "context": {
                k: v for k, v in {
                    "competition": self.context.competition,
                    "season": self.context.season,
                    "round": self.context.round,
                    "match_id": self.context.match_id,
                    "date": self.context.date,
                    "home": self.context.home,
                    "away": self.context.away,
                    "team": self.context.team,
                    "player_id": self.context.player_id,
                    "event_id": self.context.event_id,
                    "minute": self.context.minute,
                    "second": self.context.second,
                }.items() if v is not None
            },
            "provenance": self.provenance.questions(),
            "temporal": {
                "valid_from": self.temporal.valid_from,
                "valid_to": self.temporal.valid_to,
                "superseded_by": self.temporal.superseded_by,
                "current": self.temporal.is_current(),
            },
        }


def make_record(
    kind: str, value: Any, layer: Layer, context: Context, provenance: Provenance,
    temporal: Temporal | None = None,
) -> KnowledgeRecord:
    """Build a record, validating its provenance and derivation up front.

    The single front door for creating knowledge: a record that cannot answer
    *where did you come from?* — or an inferred record that cannot answer *what
    evidence are you built on?* — is rejected before it ever enters the store.
    """
    record = KnowledgeRecord(
        kind=kind, value=value, layer=layer, context=context,
        provenance=provenance, temporal=temporal or Temporal(),
    )
    check_provenance(record)
    check_derivation_evidence(record)
    return record


# --------------------------------------------------------------------------- #
# Defensive validators — prevent bad combinations by architecture, not vibes
# --------------------------------------------------------------------------- #
def check_provenance(record: KnowledgeRecord) -> None:
    """Every datum must name a source (§Proveniência Completa)."""
    if not record.provenance.source:
        raise IntegrityError(
            f"record {record.kind!r} has no source — no datum may exist without "
            f"provenance"
        )


def check_derivation_evidence(record: KnowledgeRecord) -> None:
    """Inferred data must stay linked to the evidence that produced it.

    A derived/probabilistic/simulated/experimental datum has to cite either the
    parent records it was computed from or the pipeline version that produced it
    — otherwise it is an untraceable claim, which the vision forbids.
    """
    if record.layer in INFERRED_LAYERS:
        prov = record.provenance
        if not prov.parents and not prov.pipeline_version:
            raise IntegrityError(
                f"{record.layer.value} record {record.kind!r} cites no evidence: "
                f"inferred data must link to parent records or a pipeline version"
            )


def assert_single_match(records) -> None:
    """No datum from a different match may sit in a single-match collection.

    *A pass only means something inside its own match* — combining events across
    fixtures is the cardinal isolation error, so it fails loudly.
    """
    match_ids = {r.context.match_id for r in records if r.context.match_id is not None}
    if len(match_ids) > 1:
        raise IntegrityError(
            f"records span multiple matches {sorted(match_ids)} — events from "
            f"different games must never be combined"
        )


def assert_single_season(records) -> None:
    """Statistics from different (competition, season) must stay separated."""
    seasons = {
        (r.context.competition, r.context.season)
        for r in records
        if r.context.competition is not None or r.context.season is not None
    }
    if len(seasons) > 1:
        raise IntegrityError(
            f"records span multiple competition/seasons {sorted(map(str, seasons))} "
            f"— distinct seasons must remain separate"
        )


def assert_single_layer(records) -> None:
    """A fused/aggregated group must be homogeneous in its knowledge domain."""
    layers = {r.layer for r in records}
    if len(layers) > 1:
        raise IntegrityError(
            f"records mix layers {sorted(l.value for l in layers)} — a single "
            f"knowledge unit must stay within one domain"
        )


def assert_no_fact_inference_mix(records) -> None:
    """Observed reality and model output must never be merged as one datum.

    *Simulated data is never confused with observed data.* If a collection mixes
    a factual layer with an inferred one, that is the confusion the contract
    exists to prevent.
    """
    has_fact = any(r.layer in FACTUAL_LAYERS for r in records)
    has_inferred = any(r.layer in INFERRED_LAYERS for r in records)
    if has_fact and has_inferred:
        raise IntegrityError(
            "records mix factual and inferred layers — observed reality and "
            "model output must never be combined into one datum"
        )


def assert_player_single_team(records) -> None:
    """A player cannot belong to two teams in the same match (referential).

    Checked per match, so the same player legitimately switching clubs across
    fixtures is fine — only a within-match contradiction fails.
    """
    seen: dict[tuple, str] = {}
    for r in records:
        pid, team, mid = r.context.player_id, r.context.team, r.context.match_id
        if pid is None or team is None or mid is None:
            continue
        prior = seen.get((mid, pid))
        if prior is not None and prior != team:
            raise IntegrityError(
                f"player {pid} appears for both {prior!r} and {team!r} in match "
                f"{mid} — a player cannot be on two teams in one match"
            )
        seen[(mid, pid)] = team


def check_referential_integrity(
    records, known_players=None, known_matches=None
) -> None:
    """Relationships must resolve to valid entities (§Integridade Referencial).

    * an event (anything anchored to a minute/event) must belong to a match;
    * a datum about a player must reference a known player, when a roster is
      supplied;
    * a datum about a match must reference a known match, when a catalog is
      supplied.

    ``known_*`` are optional: without them the entity-existence checks are
    skipped (you cannot validate against a reference you did not provide), but
    the structural "an event needs a match" rule always holds.
    """
    for r in records:
        ctx = r.context
        is_event = ctx.event_id is not None or ctx.minute is not None
        if is_event and ctx.match_id is None:
            raise IntegrityError(
                f"record {r.kind!r} is anchored in time but has no match — an "
                f"event cannot exist without a match"
            )
        if known_players is not None and ctx.player_id is not None:
            if ctx.player_id not in known_players:
                raise IntegrityError(
                    f"record {r.kind!r} references unknown player {ctx.player_id!r} "
                    f"— a datum cannot point at a player that does not exist"
                )
        if known_matches is not None and ctx.match_id is not None:
            if ctx.match_id not in known_matches:
                raise IntegrityError(
                    f"record {r.kind!r} references unknown match {ctx.match_id!r}"
                )


def check_chronology(ordered_records) -> None:
    """Event minutes must not run backwards in their given order.

    ``ordered_records`` is the event sequence as recorded; their ``context.minute``
    values must be non-decreasing. A later event with an earlier minute means the
    stream's clock is inconsistent — caught before it corrupts anything downstream.
    """
    last = None
    last_kind = None
    for r in ordered_records:
        minute = r.context.minute
        if minute is None:
            continue
        if last is not None and minute < last:
            raise IntegrityError(
                f"chronology violated: {r.kind!r} at minute {minute} follows "
                f"{last_kind!r} at minute {last}"
            )
        last, last_kind = minute, r.kind


def check_aggregate_consistency(aggregate: KnowledgeRecord, event_records) -> None:
    """An aggregate must equal the individual events it summarizes.

    *Aggregated statistics must be consistent with the individual events.* If a
    fused "7 corners" does not match the 7 corner events on record, one of them
    is wrong and the contradiction is surfaced rather than stored.
    """
    expected = aggregate.value
    if not isinstance(expected, (int, float)):
        raise IntegrityError(
            f"aggregate {aggregate.kind!r} is not numeric ({expected!r}); cannot "
            f"reconcile against events"
        )
    observed = len(list(event_records))
    if int(expected) != observed:
        raise IntegrityError(
            f"aggregate {aggregate.kind!r}={expected} disagrees with {observed} "
            f"underlying events — aggregate and events must be consistent"
        )


def safe_to_fuse(records) -> None:
    """Guard the moment before a fuse: same target, different sources, one layer.

    Fusion combines *independent views of the same thing*. This refuses to fuse
    records that describe different things (different logical target), that come
    from a single source (nothing to cross-check), or that straddle the
    fact/inference divide — the exact preconditions ``fie.fusion.fuse_field``
    silently assumes, now enforced.
    """
    records = list(records)
    if len(records) < 2:
        raise IntegrityError("need at least two records to fuse")
    assert_single_layer(records)
    assert_no_fact_inference_mix(records)
    targets = {(r.layer, r.kind, r.context.key()) for r in records}
    if len(targets) > 1:
        raise IntegrityError(
            "refusing to fuse records that describe different things — fusion "
            "reconciles independent views of the *same* datum"
        )
    sources = {r.provenance.source for r in records}
    if len(sources) < 2:
        raise IntegrityError(
            f"only one source {sorted(sources)} — fusion needs independent "
            f"providers to cross-check"
        )


def assert_integrity(records, *, single_match=False, single_season=False,
                     known_players=None, known_matches=None) -> None:
    """Run the always-on structural checks over a record collection.

    Referential integrity and the player/single-team rule always apply; match
    and season isolation are opt-in because a legitimate cross-match/-season
    collection (a player's career, a league table) is not a violation.
    """
    records = list(records)
    for r in records:
        check_provenance(r)
        check_derivation_evidence(r)
    assert_player_single_team(records)
    check_referential_integrity(records, known_players, known_matches)
    if single_match:
        assert_single_match(records)
    if single_season:
        assert_single_season(records)


# --------------------------------------------------------------------------- #
# Bridge — lift the existing match-fusion output into knowledge records
# --------------------------------------------------------------------------- #
def from_fused_fields(
    fused: dict, context: Context, provenance: Provenance,
    temporal: Temporal | None = None,
) -> list:
    """Turn ``fie.fusion.fuse_match`` output into observed knowledge records.

    Each fused field becomes one OBSERVED :class:`KnowledgeRecord` whose value
    keeps the fused number *and* its provenance (winning sources, per-field
    confidence, recorded dissent) — so the match-reconciliation FUT-K already
    ships slots into the unified substrate with its honesty intact. Metadata
    keys (``_conflicts``, ``_sources``) are skipped.
    """
    out = []
    for field_name, cell in fused.items():
        if field_name.startswith("_"):
            continue
        prov = provenance.with_transformation(f"fuse:{field_name}")
        out.append(make_record(
            kind=field_name,
            value={
                "value": cell.get("value"),
                "confidence": cell.get("confidence"),
                "sources": cell.get("sources"),
                "dissent": cell.get("dissent"),
                "agreed": cell.get("agreed"),
            },
            layer=Layer.OBSERVED,
            context=context,
            provenance=prov,
            temporal=temporal,
        ))
    return out
