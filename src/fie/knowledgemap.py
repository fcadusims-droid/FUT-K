"""Lift engine outputs into the Dataset Fusion contract (Inference, Phase C).

The engine already produces probabilistic, simulated and derived knowledge — the
panel's predictions, the Future Simulation's distribution, player profiles, match
embeddings. Phase C adds **no new math**: it wraps those existing outputs as
:class:`fie.fusiondata.KnowledgeRecord` in the right layer, each **citing the
evidence that produced it** (the model/pipeline version, and any parent records),
so a probability, a simulated outcome and a derived profile all sit in the store
under the same isolation and provenance rules as an observed fact — and can never
be confused with one.

Pure and deterministic: same output dict + context, same records, same ids.
Standard library only; every record goes through ``make_record``, which refuses
an inferred datum that cites no evidence.
"""

from __future__ import annotations

from typing import Optional

from .fusiondata import Context, Layer, Provenance, Temporal, make_record

# Pipeline identifiers — the "which model produced this?" provenance answer.
PRED_PIPELINE = "prediction/poisson"
SIM_PIPELINE = "simulation/montecarlo"
PROFILE_PIPELINE = "profiling/dna"
EMBED_PIPELINE = "similarity/vector"


def prediction_records(
    predictions: dict, context: Context, *,
    pipeline_version: str = PRED_PIPELINE, confidence: Optional[float] = None,
    parents: tuple = (),
) -> list:
    """Wrap a panel's ``predictions`` dict as PROBABILISTIC records.

    One record per predicted target (``goal_next_5min``, ``goal_next_10min``,
    ``goal_before_half``, ``next_goal``). The panel-level ``confidence`` rides in
    each record's temporal metadata — the model's own honesty, carried into the
    store. Estimates are point-in-time, so ``context`` should pin the minute.
    """
    out = []
    for target in ("goal_next_5min", "goal_next_10min", "goal_before_half",
                   "next_goal"):
        if target not in predictions:
            continue
        out.append(make_record(
            kind=f"pred_{target}",
            value=predictions[target],
            layer=Layer.PROBABILISTIC,
            context=context,
            provenance=Provenance(source="engine", pipeline_version=pipeline_version,
                                  parents=tuple(parents)),
            temporal=Temporal(confidence=confidence),
        ))
    return out


def simulation_records(
    sim: dict, context: Context, *,
    pipeline_version: str = SIM_PIPELINE, parents: tuple = (),
) -> list:
    """Wrap a Future Simulation result as SIMULATED records.

    The outcome distribution, expected goals, goal probability, likeliest
    scorelines and opportunity windows — each an independent simulated datum. The
    seed and sim count travel in provenance (``source_version``) so any record is
    reproducible; nothing here is ever mistaken for an observed fact.
    """
    seed = sim.get("seed")
    n_sims = sim.get("n_sims")
    source_version = f"seed={seed};n_sims={n_sims}"
    prov = Provenance(source="simulation", pipeline_version=pipeline_version,
                      source_version=source_version, parents=tuple(parents))
    out = []
    for key in ("outcome", "expected_goals", "goal_prob", "scorelines",
                "opportunity_windows"):
        if key not in sim:
            continue
        out.append(make_record(
            kind=f"sim_{key}", value=sim[key], layer=Layer.SIMULATED,
            context=context, provenance=prov,
        ))
    return out


def profile_record(
    profile: dict, context: Context, *,
    pipeline_version: str = PROFILE_PIPELINE, parents: tuple = (),
    confidence: Optional[float] = None,
) -> "object":
    """Wrap a player's technical profile as one DERIVED record (its DNA)."""
    return make_record(
        kind="player_profile", value=profile, layer=Layer.DERIVED, context=context,
        provenance=Provenance(source="engine", pipeline_version=pipeline_version,
                              parents=tuple(parents)),
        temporal=Temporal(confidence=confidence),
    )


def embedding_record(
    vector, context: Context, *, kind: str = "match_vector",
    pipeline_version: str = EMBED_PIPELINE, parents: tuple = (),
) -> "object":
    """Wrap a computed embedding/feature vector as one DERIVED record."""
    return make_record(
        kind=kind, value=list(vector), layer=Layer.DERIVED, context=context,
        provenance=Provenance(source="engine", pipeline_version=pipeline_version,
                              parents=tuple(parents)),
    )
