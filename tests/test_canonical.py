"""Canonical layer — source-agnostic ids, identity resolution, staged records."""

from __future__ import annotations

from fie.canonical import (
    Stage,
    canonical_match_id,
    canonical_player_id,
    canonical_record,
    canonical_team_id,
    canonicalize_match,
    normalize_person,
    raw_record,
    stage_of,
)
from fie.fusiondata import Context, Layer


# --------------------------------------------------------------------------- #
# Global ids: stable across a provider's spelling
# --------------------------------------------------------------------------- #
def test_team_id_is_stable_across_spellings():
    assert canonical_team_id("Bayer 04 Leverkusen") == canonical_team_id("Leverkusen")
    assert canonical_team_id("Atlético de Madrid") == canonical_team_id("Ath Madrid")
    assert canonical_team_id("Bayern") != canonical_team_id("Dortmund")


def test_match_id_is_the_same_fixture_across_providers():
    a = canonical_match_id("2023-08-19", "Leverkusen", "RB Leipzig")
    b = canonical_match_id("2023-08-19", "Bayer 04 Leverkusen", "Leipzig")
    assert a == b


# --------------------------------------------------------------------------- #
# Identity resolution: merge the same person only on shared evidence
# --------------------------------------------------------------------------- #
def test_player_merges_on_shared_external_id():
    # Two providers, different spellings, same Wikidata QID -> one id.
    a = canonical_player_id("Kaká", external_id="Q131237")
    b = canonical_player_id("Ricardo Izecson dos Santos Leite", external_id="Q131237")
    assert a == b


def test_player_merges_on_name_plus_birthdate():
    a = canonical_player_id("Kaká", birth_date="1982-04-22")
    b = canonical_player_id("Kaka", birth_date="1982-04-22")   # accent-insensitive
    assert a == b
    # Same name, different birth date -> two different people, not merged.
    assert canonical_player_id("John Smith", birth_date="1990-01-01") != \
        canonical_player_id("John Smith", birth_date="1992-02-02")


def test_alias_table_resolves_known_hard_cases():
    assert normalize_person("R. Kaká") == "kaka"
    assert normalize_person("Ricardo Izecson dos Santos Leite") == "kaka"
    # And so the ids match without a shared key, via the alias registry.
    assert canonical_player_id("R. Kaká") == canonical_player_id("Kaká")


def test_ambiguous_names_are_not_guessed_apart():
    # No birth date, no external id, different normalized names -> different ids
    # (we never fabricate a merge we can't justify).
    assert canonical_player_id("J. Silva") != canonical_player_id("Carlos Silva")


# --------------------------------------------------------------------------- #
# Staged records: raw kept intact, canonical source-agnostic, stage auditable
# --------------------------------------------------------------------------- #
def test_raw_record_is_kept_intact_and_tagged():
    payload = {"weird_provider_field": 42, "player": "X"}
    r = raw_record(payload, source="opta", kind="raw_match",
                   context=Context(match_id="m1"), collected_at="2024-01-01")
    assert r.value == payload                       # never modified
    assert r.layer is Layer.EXTERNAL
    assert stage_of(r) is Stage.RAW


def test_canonical_record_is_source_agnostic_but_traceable():
    r = canonical_record("match_goals", 3, context=Context(match_id="m1"),
                         source="statsbomb")
    assert stage_of(r) is Stage.CANONICAL
    assert r.provenance.source == "statsbomb"        # traceable to origin
    assert r.layer is Layer.OBSERVED


def test_canonicalize_match_gives_futk_ids():
    raw = {"date": "2023-08-19", "home": "Leverkusen", "away": "RB Leipzig",
           "home_goals": 3, "away_goals": 2, "competition": "BL1"}
    rec = canonicalize_match(raw, source="football_data")
    assert rec.context.match_id == canonical_match_id("2023-08-19",
                                                      "Leverkusen", "RB Leipzig")
    assert rec.value["home_team_id"] == canonical_team_id("Leverkusen")
    assert rec.value["home_goals"] == 3
    assert stage_of(rec) is Stage.CANONICAL
    # Deterministic.
    assert canonicalize_match(dict(raw), source="football_data").id == rec.id
