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


def test_normalization_strips_digit_tokens_and_new_leagues():
    from fie.fusion import normalize_entity as n
    assert n("1. FC Heidenheim 1846") == "heidenheim"
    assert n("1. FC Union Berlin") == "union berlin"
    assert n("FSV Mainz 05") == "mainz"
    assert n("FC Bayern München") == "bayern munich"
    assert n("Nott'm Forest") == "nottingham forest"
    assert n("Paris SG") == n("PSG") == "paris saint germain"
    assert n("Inter Milan") == n("FC Internazionale Milano") == "internazionale"


def test_estimate_offset_recovers_clock_shift():
    from fie.fusion import estimate_offset
    a = [12.0, 47.5, 80.0]
    b = [t + 1.4 for t in a]              # source B's clock runs 1.4 min late
    assert abs(estimate_offset(a, b) - 1.4) < 1e-9
    # Unequal anchor counts: extra unmatched anchor is ignored.
    assert abs(estimate_offset(a, b + [200.0]) - 1.4) < 1e-9
    assert estimate_offset([], [10.0]) == 0.0  # no pairs -> assume aligned


def test_align_timelines_unifies_clocks():
    from fie.fusion import align_timelines
    a = [{"minute": 12.0, "type": "goal"}, {"minute": 30.0, "type": "shot"}]
    b = [{"minute": 13.5, "type": "goal"}, {"minute": 20.5, "type": "corner"}]
    out = align_timelines({"alpha": a, "beta": b})
    assert out["offsets"] == {"alpha": 0.0, "beta": 1.5}
    minutes = [e["aligned_minute"] for e in out["timeline"]]
    assert minutes == sorted(minutes)
    goals = [e for e in out["timeline"] if e["type"] == "goal"]
    # After alignment the two views of the same goal land on the same minute.
    assert abs(goals[0]["aligned_minute"] - goals[1]["aligned_minute"]) < 1e-9
    # Deterministic:
    assert align_timelines({"alpha": a, "beta": b}) == out


def test_normalization_structural_tokens_premier_league():
    # football-data short names vs openfootball "<Club> FC" long names.
    from fie.fusion import normalize_entity as n
    assert n("Arsenal FC") == n("Arsenal") == "arsenal"
    assert n("AFC Bournemouth") == n("Bournemouth") == "bournemouth"
    assert n("Brighton & Hove Albion FC") == n("Brighton") == "brighton"
    assert n("Luton Town FC") == n("Luton") == "luton town"
    assert n("West Ham United FC") == n("West Ham") == "west ham united"
    assert n("Wolverhampton Wanderers FC") == n("Wolves")
    assert n("Real Madrid CF") == n("Real Madrid") == "real madrid"
    assert n("Sheffield United FC") == n("Sheffield United") == "sheffield united"


def test_priors_from_agreement_scores_sources_against_majority():
    from fie.fusion import priors_from_agreement

    # Source c dissents once out of two compared fields; a and b always agree.
    sources = {
        "a": [{"date": "2024-01-01", "home": "X", "away": "Y",
               "goals": 2, "corners": 5}],
        "b": [{"date": "2024-01-01", "home": "X", "away": "Y",
               "goals": 2, "corners": 5}],
        "c": [{"date": "2024-01-01", "home": "X", "away": "Y",
               "goals": 2, "corners": 7}],
    }
    resolved = resolve_matches(sources)
    fields = {"goals": 0, "corners": 0}
    measured = priors_from_agreement(resolved, fields, priors={})
    assert measured == {"a": 1.0, "b": 1.0, "c": 0.5}

    # Deterministic and pure: same inputs, same output.
    assert priors_from_agreement(resolved, fields, priors={}) == measured

    # A source never compared against anyone yields no score.
    lonely = resolve_matches({"solo": sources["a"]})
    assert priors_from_agreement(lonely, fields, priors={}) == {}
