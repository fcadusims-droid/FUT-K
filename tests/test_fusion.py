"""Data Fusion Layer — deterministic multi-source reconciliation."""

from __future__ import annotations

from fie.fusion import (
    agreement_report,
    fuse_field,
    fuse_match,
    normalize_entity,
    resolve_matches,
)


def test_entity_resolution_aliases_and_accents():
    assert normalize_entity("Atlético de Madrid") == "atletico madrid"
    assert normalize_entity("Ath Madrid") == "atletico madrid"
    assert normalize_entity("Bayer 04 Leverkusen") == "bayer leverkusen"
    assert normalize_entity("Leverkusen") == "bayer leverkusen"
    assert normalize_entity("M'gladbach") == normalize_entity("Borussia Mönchengladbach") \
        or normalize_entity("M'gladbach") == "borussia monchengladbach"
    assert normalize_entity("") == ""


def test_match_resolution_across_sources():
    a = [{"date": "2023-08-19", "home": "Leverkusen", "away": "RB Leipzig", "hg": 3}]
    b = [{"date": "2023-08-19", "home": "Bayer 04 Leverkusen", "away": "Leipzig", "hg": 3},
         {"date": "2023-08-20", "home": "Bayern Munich", "away": "Augsburg", "hg": 2}]
    resolved = resolve_matches({"fd": a, "sb": b})
    assert len(resolved) == 2
    both = [f for f in resolved if len(f["records"]) == 2]
    assert len(both) == 1
    assert both[0]["key"] == ("2023-08-19", "bayer leverkusen", "leipzig")


def test_fuse_field_agreement_and_conflict():
    # Full agreement -> confidence 1.0.
    agree = fuse_field({"a": 2, "b": 2, "c": 2}, priors={})
    assert agree["value"] == 2 and agree["confidence"] == 1.0 and agree["agreed"]

    # 2v1 conflict: majority weight wins; dissent is recorded.
    conflict = fuse_field({"a": 2, "b": 2, "c": 3}, priors={})
    assert conflict["value"] == 2 and not conflict["agreed"]
    assert conflict["dissent"] == {"c": 3}
    assert abs(conflict["confidence"] - 2 / 3) < 0.01

    # Priors break a 1v1 tie toward the more reliable source.
    tie = fuse_field({"a": 1, "b": 0}, priors={"a": 0.9, "b": 0.6})
    assert tie["value"] == 1 and tie["sources"] == ["a"]

    # Numeric tolerance: coordinates within 0.5 agree, mean is reported.
    coords = fuse_field({"a": 41.3, "b": 41.1}, priors={}, tolerance=0.5)
    assert coords["agreed"] and abs(coords["value"] - 41.2) < 1e-9


def test_fuse_field_determinism():
    values = {"x": 5, "y": 7, "z": 5}
    first = fuse_field(values, priors={"x": 0.8, "y": 0.9, "z": 0.7})
    for _ in range(5):
        assert fuse_field(dict(values), priors={"x": 0.8, "y": 0.9, "z": 0.7}) == first


def test_fuse_match_and_agreement_report():
    sources = {
        "sb": [{"date": "2023-08-19", "home": "Leverkusen", "away": "Leipzig",
                "home_goals": 3, "away_goals": 2, "corners": 7}],
        "fd": [{"date": "2023-08-19", "home": "Bayer 04 Leverkusen", "away": "RB Leipzig",
                "home_goals": 3, "away_goals": 2, "corners": 8}],
    }
    resolved = resolve_matches(sources)
    fields = {"home_goals": 0, "away_goals": 0, "corners": 0}
    unified = fuse_match(resolved[0]["records"], fields, priors={"sb": 0.95, "fd": 0.9})
    assert unified["home_goals"]["value"] == 3 and unified["home_goals"]["agreed"]
    assert unified["corners"]["value"] == 7          # sb wins the tie by prior
    assert unified["_conflicts"] == ["corners"]

    report = agreement_report(resolved, fields, priors={"sb": 0.95, "fd": 0.9})
    assert report["home_goals"]["rate"] == 1.0
    assert report["corners"]["rate"] == 0.0
    assert report["corners"]["compared"] == 1
