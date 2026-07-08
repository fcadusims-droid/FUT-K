"""Canonical layer — the source-agnostic FUT-K dataset (Inference).

The architecture rule of the Dataset Fusion: **no FUT-K module consumes external
data directly.** Everything from an outside provider (StatsBomb, Opta, FBref,
Transfermarkt, a CSV…) passes through one pipeline —

    Raw  ->  Normalized  ->  Canonical

— and only the **canonical** representation is used by simulation, scouting,
tactics, the knowledge graph and the rest of FUT-K. The consumers never learn
which provider a fact came from, so swapping StatsBomb for Opta in five years
changes nothing downstream: they depend on the canonical dataset, not the source.

This module makes those stages explicit and gives FUT-K its own identity:

* **Raw** — a record kept exactly as it arrived, never modified (``raw_record``).
* **Normalized** — the same values under unified field/entity names.
* **Canonical** — FUT-K's own global ids (``canonical_*_id``), reached by
  **identity resolution** that merges the same real entity across sources
  (Kaká / R. Kaká / Ricardo Izecson dos Santos Leite → one id) only on shared
  evidence — a common external key or name+birth-date — never on a fuzzy guess.

Everything is a pure, deterministic function; standard library only.
"""

from __future__ import annotations

import hashlib
import unicodedata
from enum import Enum
from typing import Optional

from .fusiondata import (
    Context,
    KnowledgeRecord,
    Layer,
    Provenance,
    Temporal,
    make_record,
)
from .fusion import normalize_entity


class Stage(str, Enum):
    """Where a datum sits in the ingestion pipeline (orthogonal to ``Layer``)."""

    RAW = "raw"                # exactly as it arrived; never modified
    NORMALIZED = "normalized"  # same values, unified field/entity names
    CANONICAL = "canonical"    # FUT-K's own ids, validated, cross-checked


# Known player aliases -> a canonical key, mirroring fusion.TEAM_ALIASES. Extend
# as sources introduce new spellings; keys are in normalized (lowercase, no
# accents) form. This is the deterministic, auditable path for the hard cases
# that name+birth-date cannot merge on its own.
PLAYER_ALIASES = {
    "r kaka": "kaka",
    "ricardo izecson dos santos leite": "kaka",
    "ronaldinho gaucho": "ronaldinho",
    "ronaldo de assis moreira": "ronaldinho",
}


def normalize_person(name: str) -> str:
    """Canonical key for a person's name: casefold, strip accents/punctuation."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    tokens = text.lower().replace(".", " ").replace("-", " ").split()
    key = " ".join(tokens)
    return PLAYER_ALIASES.get(key, key)


def _hash_id(prefix: str, key: str) -> str:
    return prefix + "_" + hashlib.sha256(key.encode()).hexdigest()[:16]


def canonical_team_id(name: str) -> str:
    """FUT-K's own team id, stable across every provider's spelling."""
    return _hash_id("team", normalize_entity(name))


def canonical_player_id(name: str, birth_date: Optional[str] = None,
                        external_id: Optional[str] = None) -> str:
    """FUT-K's own player id — merges the same person across sources on evidence.

    Resolution order, strongest first:

    * a shared **external id** (e.g. a Wikidata QID) → one id, unambiguously;
    * **name + birth date** → one id (two providers naming the same DOB are the
      same person);
    * otherwise the **normalized name** (with the alias table) — and if two real
      people share a name with no birth date to separate them, they are *not*
      guessed apart here; that ambiguity is surfaced, not silently merged wrong.
    """
    if external_id:
        return _hash_id("player", f"ext:{external_id}")
    key = normalize_person(name)
    if birth_date:
        return _hash_id("player", f"{key}|{birth_date}")
    return _hash_id("player", f"name:{key}")


def canonical_match_id(date: str, home: str, away: str) -> str:
    """FUT-K's own fixture id from its canonical identity (date + both teams)."""
    return _hash_id("match", f"{date}|{normalize_entity(home)}|{normalize_entity(away)}")


def canonical_competition_id(name: str) -> str:
    return _hash_id("competition", normalize_entity(name))


# --------------------------------------------------------------------------- #
# Records at each stage — provenance carries the stage tag, so a datum's place
# in the pipeline is always auditable.
# --------------------------------------------------------------------------- #
def _staged(provenance: Provenance, stage: Stage) -> Provenance:
    return provenance.with_transformation(f"stage:{stage.value}")


def raw_record(payload, *, source: str, kind: str, context: Context,
               collected_at: Optional[str] = None,
               source_version: Optional[str] = None) -> KnowledgeRecord:
    """A datum kept **exactly as it arrived** — the Raw layer, never modified.

    Stored in the ``EXTERNAL`` domain and tagged ``stage:raw`` in provenance, so
    the untouched provider payload is always recoverable for audit. Downstream
    modules never read this; only the pipeline does.
    """
    return make_record(
        kind=kind, value=payload, layer=Layer.EXTERNAL, context=context,
        provenance=_staged(
            Provenance(source=source, collected_at=collected_at,
                       source_version=source_version, ingested_by="ingestion"),
            Stage.RAW,
        ),
    )


def canonical_record(kind: str, value, *, context: Context, source: str,
                     layer: Layer = Layer.OBSERVED,
                     collected_at: Optional[str] = None,
                     parents: tuple = (), temporal: Temporal | None = None
                     ) -> KnowledgeRecord:
    """A validated, source-agnostic datum — the Canonical layer.

    Provenance still records which source it came from (traceability), but its
    context carries FUT-K's own ids, so consumers depend on the canonical dataset
    and not on the provider. Tagged ``stage:canonical``.
    """
    return make_record(
        kind=kind, value=value, layer=layer, context=context,
        provenance=_staged(
            Provenance(source=source, collected_at=collected_at,
                       ingested_by="ingestion", parents=tuple(parents)),
            Stage.CANONICAL,
        ),
        temporal=temporal,
    )


def stage_of(record: KnowledgeRecord) -> Optional[Stage]:
    """The pipeline stage a record was emitted at (from its provenance tag)."""
    for t in record.provenance.transformations:
        if t.startswith("stage:"):
            try:
                return Stage(t.split(":", 1)[1])
            except ValueError:
                return None
    return None


def canonicalize_match(raw: dict, *, source: str,
                       collected_at: Optional[str] = None) -> KnowledgeRecord:
    """Normalize + resolve one raw match record into a canonical match datum.

    ``raw`` has ``date``/``home``/``away`` (+ any stats). The output's context
    uses FUT-K's canonical match and competition ids, so a fixture is one entity
    no matter which provider reported it. Deterministic.
    """
    date = raw.get("date") or ""
    home = raw.get("home") or ""
    away = raw.get("away") or ""
    match_id = canonical_match_id(date, home, away)
    context = Context(
        match_id=match_id, date=date,
        home=normalize_entity(home), away=normalize_entity(away),
        competition=raw.get("competition"),
    )
    value = {k: v for k, v in raw.items() if k not in ("home", "away")}
    value["home_team_id"] = canonical_team_id(home)
    value["away_team_id"] = canonical_team_id(away)
    return canonical_record("match", value, context=context, source=source,
                            collected_at=collected_at)
