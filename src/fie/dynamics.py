"""Dynamic Knowledge Management — knowledge as a temporal state (Inference).

Football never holds still: players change position and club, coaches change
scheme, shirt numbers change. So FUT-K treats **every attribute as a state in
time, never a permanent fact** (docs/design/DATASET_FUSION.md §Dynamic Knowledge).
This module is the timeline machinery on top of the ``fie.fusiondata`` substrate:

* the system never *overwrites* knowledge — a change **appends a new version**
  and closes the previous one, so the full history survives (``append_version``);
* a **permanent** change (a transfer, a settled position switch) becomes the new
  current state; a **temporary** one (an in-match role, a suspension, a false-nine
  spell) is valid only inside its window and reverts when the window ends;
* any question about the past — *how did this player play three seasons ago? when
  did he stop being a striker?* — is answered by resolving the state **as of** a
  date (``state_as_of``, ``history``).

Everything is a pure, deterministic function of the version records: same
versions, same "as of" date, same answer — today and in six months. Standard
library only.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .fusiondata import (
    PERMANENT,
    TEMPORARY,
    Context,
    IntegrityError,
    KnowledgeRecord,
    Layer,
    Provenance,
    Temporal,
    make_record,
)


def entity_id(context: Context) -> Optional[str]:
    """The entity a datum is about: a player, else a team, else a match."""
    return context.player_id or context.team or context.match_id


def attribute_key(record: KnowledgeRecord) -> tuple:
    """Identity of *which attribute of which entity* a version describes.

    All versions of "player p1's position" share this key regardless of value or
    date — it is the timeline they belong to.
    """
    return (record.kind, entity_id(record.context))


def state_version(
    kind: str, value, entity: Context, source: str, *,
    valid_from: Optional[str] = None, valid_to: Optional[str] = None,
    permanence: str = PERMANENT, confidence: Optional[float] = None,
    layer: Layer = Layer.OBSERVED, collected_at: Optional[str] = None,
    pipeline_version: Optional[str] = None, parents: tuple = (),
) -> KnowledgeRecord:
    """Build one versioned state of an entity attribute (validated up front).

    ``entity`` is the context that names the entity (e.g. ``Context(player_id=…)``).
    ``permanence`` is ``PERMANENT`` or ``TEMPORARY``; ``confidence`` is how sure we
    are of this version. Goes through ``fusiondata.make_record`` so provenance and
    derivation evidence are enforced.
    """
    if permanence not in (PERMANENT, TEMPORARY):
        raise IntegrityError(
            f"permanence must be {PERMANENT!r} or {TEMPORARY!r}, got {permanence!r}"
        )
    return make_record(
        kind=kind, value=value, layer=layer, context=entity,
        provenance=Provenance(source=source, collected_at=collected_at,
                              pipeline_version=pipeline_version, parents=parents),
        temporal=Temporal(valid_from=valid_from, valid_to=valid_to,
                          permanence=permanence, confidence=confidence),
    )


def _active_at(record: KnowledgeRecord, at: str) -> bool:
    """True if ``record``'s validity window contains the date ``at``.

    ``valid_from is None`` means "since always"; ``valid_to is None`` means "still
    open". ISO ``yyyy-mm-dd`` strings compare correctly lexicographically.
    """
    vf = record.temporal.valid_from
    vt = record.temporal.valid_to
    if vf is not None and at < vf:
        return False
    if vt is not None and at >= vt:
        return False
    return True


def _rank(record: KnowledgeRecord) -> tuple:
    """Deterministic precedence among versions active on the same date.

    A temporary state overrides the permanent baseline while it is active; then
    the more recently started version wins; then the more confident; then a stable
    id tie-break. Never wall-clock, never random.
    """
    is_temp = 1 if record.temporal.is_temporary() else 0
    vf = record.temporal.valid_from or ""
    conf = record.temporal.confidence if record.temporal.confidence is not None else -1.0
    return (is_temp, vf, conf, record.id)


def versions_of(records, kind: str, entity: str) -> list:
    """Every version belonging to one (attribute, entity) timeline."""
    return [r for r in records if attribute_key(r) == (kind, entity)]


def state_as_of(records, at: str, kind: str, entity: str):
    """The state of ``entity``'s ``kind`` attribute valid on date ``at``.

    Resolves the timeline the way the simulator must read it before kick-off:
    the version whose window contains ``at``, with a temporary state overriding
    the permanent one while active. Returns the winning :class:`KnowledgeRecord`,
    or ``None`` if nothing was valid yet on that date. Deterministic.
    """
    active = [r for r in versions_of(records, kind, entity) if _active_at(r, at)]
    if not active:
        return None
    return max(active, key=_rank)


def value_as_of(records, at: str, kind: str, entity: str, default=None):
    """The value of :func:`state_as_of` (or ``default`` if none was valid)."""
    record = state_as_of(records, at, kind, entity)
    return record.value if record is not None else default


def history(records, kind: str, entity: str) -> list:
    """The full ordered version history of one (attribute, entity) timeline.

    Sorted oldest-first by start of validity — the record that answers "how did
    this player's profile evolve?" without ever having lost a past version.
    """
    return sorted(
        versions_of(records, kind, entity),
        key=lambda r: (r.temporal.valid_from or "", r.id),
    )


def current_state(records, kind: str, entity: str):
    """The latest *permanent* live version of an attribute (the settled truth).

    Ignores temporary overrides (those belong to a context, not the baseline) and
    superseded versions; returns the open permanent state with the latest start,
    or ``None``. For "the effective state on date D", use :func:`state_as_of`.
    """
    live = [
        r for r in versions_of(records, kind, entity)
        if not r.temporal.is_temporary() and r.temporal.is_current()
    ]
    if not live:
        return None
    return max(live, key=lambda r: (r.temporal.valid_from or "", r.id))


def append_version(versions, new_record: KnowledgeRecord) -> list:
    """Append a new version to a timeline the append-only way.

    A **permanent** change closes the previous permanent live version of the same
    attribute (setting its ``valid_to`` to the new start and linking
    ``superseded_by``) and becomes the new current state — the old version is kept,
    never deleted. A **temporary** change closes nothing: it coexists with the
    permanent baseline and simply overrides it while active. Returns a new list;
    the input is never mutated. Deterministic.
    """
    key = attribute_key(new_record)
    if new_record.temporal.is_temporary():
        return list(versions) + [new_record]
    out = []
    for r in versions:
        if (attribute_key(r) == key and not r.temporal.is_temporary()
                and r.temporal.is_current()):
            out.append(replace(
                r,
                temporal=r.temporal.close(
                    valid_to=new_record.temporal.valid_from or "",
                    superseded_by=new_record.id,
                ),
            ))
        else:
            out.append(r)
    out.append(new_record)
    return out


def build_timeline(versions) -> list:
    """Fold a stream of versions into a consistent, append-only timeline.

    Applies ``append_version`` in the versions' recorded order, so replaying the
    same stream always yields the same closed/superseded history — the
    deterministic reconstruction an audit or a re-ingest depends on.
    """
    timeline: list = []
    for v in versions:
        timeline = append_version(timeline, v)
    return timeline
