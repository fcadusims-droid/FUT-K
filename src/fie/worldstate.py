"""Knowledge Base for Simulation — the pre-match world state (Inference).

The simulation engine never plays in a vacuum. Before kick-off it is handed a
**knowledge state** assembled by the Dataset Fusion: the consolidated view of the
teams, players, coaches and history *as they were known before the match*
(docs/design/DATASET_FUSION.md §Knowledge Base for Simulation). Every
probabilistic decision then rests on that prior knowledge — and on nothing from
the future.

Two guarantees make a simulation a real probabilistic experiment rather than a
replay of a known result:

* **No temporal leakage.** The pre-match state is resolved *as of* a cutoff (the
  match date) through ``fie.dynamics``, so an attribute that only changed *after*
  the cutoff — or a datum collected after it — can never enter the state. This is
  the 73:15 leakage discipline (see the README) applied to the knowledge base
  itself, and ``assert_no_future_leak`` enforces it.
* **Independence of simulated output.** What a simulation produces is a separate,
  ``SIMULATED``-layer body of derived data. It never silently modifies the
  historical base or a player's profile; only after explicit validation/audit may
  it be admitted — still tagged simulated, never mistaken for observed fact
  (``simulated_record``, ``gate_incorporation``).

Pure and deterministic: same records, same cutoff, same state. Standard library
only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .dynamics import attribute_key, state_as_of
from .fusiondata import (
    FACTUAL_LAYERS,
    Context,
    IntegrityError,
    KnowledgeRecord,
    Layer,
    Provenance,
    make_record,
)

# Layers admissible as *prior knowledge* for a simulation: observed reality and
# knowledge derived from it. An unvalidated simulation must never seed another
# (that is how compounding fantasy leaks in), so SIMULATED/EXPERIMENTAL are out.
PRIOR_LAYERS = frozenset(FACTUAL_LAYERS | {Layer.DERIVED})


@dataclass(frozen=True)
class KnowledgeState:
    """The consolidated pre-match knowledge handed to the simulator.

    ``entities`` maps each entity id to its resolved attributes at ``as_of``;
    ``records`` keeps the exact versions chosen, so every value in the state is
    auditable back to its provenance. Immutable — a simulation reads it, it does
    not write to it.
    """

    as_of: str
    entities: dict           # entity_id -> {attribute: value}
    records: tuple           # the KnowledgeRecords chosen (provenance/audit)

    def get(self, entity: str, attribute: str, default=None):
        return self.entities.get(entity, {}).get(attribute, default)

    def attributes(self, entity: str) -> dict:
        return dict(self.entities.get(entity, {}))


def assert_no_future_leak(records, as_of: str) -> None:
    """Refuse any datum the simulator could not have known at ``as_of``.

    A record leaks the future if it becomes valid after the cutoff, if it was
    collected after the cutoff, or if it is unvalidated inference (simulated /
    experimental). Raises :class:`IntegrityError` on the first leak — the
    knowledge-base twin of the erase-the-future test.
    """
    for r in records:
        vf = r.temporal.valid_from
        if vf is not None and vf > as_of:
            raise IntegrityError(
                f"leakage: {r.kind!r} becomes valid at {vf}, after the {as_of} "
                f"cutoff — a pre-match state cannot know it"
            )
        collected = r.provenance.collected_at
        if collected is not None and collected > as_of:
            raise IntegrityError(
                f"leakage: {r.kind!r} was collected at {collected}, after the "
                f"{as_of} cutoff"
            )
        if r.layer not in PRIOR_LAYERS:
            raise IntegrityError(
                f"{r.layer.value} record {r.kind!r} cannot seed a simulation — "
                f"only observed/historical/youth/external/derived prior knowledge "
                f"may"
            )


def assemble_state(records, as_of: str, *, entities=None) -> KnowledgeState:
    """Build the leakage-free pre-match knowledge state as of ``as_of``.

    For every (attribute, entity) timeline present in ``records`` — optionally
    restricted to ``entities`` — takes the version valid at the cutoff via
    ``fie.dynamics.state_as_of`` (temporary overrides honoured), skipping any
    layer that may not seed a simulation. The chosen records are re-checked with
    ``assert_no_future_leak`` before the state is returned, so leakage is
    impossible by construction. Deterministic.
    """
    prior = [r for r in records if r.layer in PRIOR_LAYERS]
    keys = sorted({attribute_key(r) for r in prior},
                  key=lambda k: (k[0], k[1] or ""))
    chosen: list = []
    built: dict = {}
    for kind, ent in keys:
        if entities is not None and ent not in entities:
            continue
        winner = state_as_of(prior, as_of, kind, ent)
        if winner is None:
            continue
        chosen.append(winner)
        built.setdefault(ent, {})[kind] = winner.value
    assert_no_future_leak(chosen, as_of)
    return KnowledgeState(as_of=as_of, entities=built, records=tuple(chosen))


# --------------------------------------------------------------------------- #
# Simulated output — independent, and admitted only after audit
# --------------------------------------------------------------------------- #
def simulated_record(
    kind: str, value, context: Context, *,
    pipeline_version: str, parents: tuple = (), produced_at: Optional[str] = None,
    state: KnowledgeState | None = None,
) -> KnowledgeRecord:
    """Wrap one simulation output as an independent ``SIMULATED`` record.

    Cites the model (``pipeline_version``) and the evidence it ran on — either the
    supplied ``parents`` or, if a :class:`KnowledgeState` is given, the ids of the
    exact prior-knowledge records that seeded it. So a simulated datum always
    answers *what was I computed from?* and can never be confused with an observed
    fact. Validated by ``fusiondata.make_record``.
    """
    seed_ids = tuple(r.id for r in state.records) if state is not None else ()
    all_parents = tuple(dict.fromkeys(parents + seed_ids))
    return make_record(
        kind=kind, value=value, layer=Layer.SIMULATED, context=context,
        provenance=Provenance(source="simulation", collected_at=produced_at,
                              pipeline_version=pipeline_version, parents=all_parents),
    )


def gate_incorporation(sim_records, *, audited: bool) -> list:
    """The gate every simulated datum passes before entering the Dataset Fusion.

    Simulation output is a separate body of derived data; it is **not** admitted
    automatically. Without an ``audited`` verdict this raises; with one it returns
    the records still in the ``SIMULATED`` layer (the separation from observed fact
    is preserved) but stamped with an ``audit:passed`` transformation, so the
    admission itself is provenance-tracked.
    """
    sim_records = list(sim_records)
    for r in sim_records:
        if r.layer is not Layer.SIMULATED:
            raise IntegrityError(
                f"gate_incorporation only admits SIMULATED records; got "
                f"{r.layer.value} {r.kind!r}"
            )
    if not audited:
        raise IntegrityError(
            "simulated data cannot enter the Dataset Fusion without validation "
            "and audit — results stay independent until then"
        )
    from dataclasses import replace

    return [
        replace(r, provenance=r.provenance.with_transformation("audit:passed"))
        for r in sim_records
    ]
