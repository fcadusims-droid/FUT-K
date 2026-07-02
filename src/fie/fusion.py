"""Football Data Fusion Layer (Inference): many sources, one truth.

No provider sees the whole game. This layer treats datasets as **sources of
evidence** and reconciles them deterministically — the design doc's consensus
idea (Section 16) turned into infrastructure:

    source A record ─┐
    source B record ─┼─> entity resolution -> match resolution ->
    source C record ─┘   field comparison -> weighted fusion ->
                          unified record + per-field confidence + provenance

Everything here is a pure function: same inputs, same output, today and in six
months. No I/O, no LLMs, no randomness — connectors (Application layer) feed
it plain dicts. Per-source reliability is expressed as explicit priors and
*measured* agreement rates, never vibes.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict

# --------------------------------------------------------------------------- #
# Entity resolution — teams (players/referees follow the same pattern)
# --------------------------------------------------------------------------- #
# Canonical aliases for cross-provider team naming. Keys and values are in
# normalized form (lowercase, no accents). Extend per league as sources grow.
TEAM_ALIASES = {
    "ath madrid": "atletico madrid",
    "atletico de madrid": "atletico madrid",
    "ath bilbao": "athletic bilbao",
    "athletic club": "athletic bilbao",
    "espanol": "espanyol",
    "rcd espanyol": "espanyol",
    "sociedad": "real sociedad",
    "betis": "real betis",
    "celta": "celta vigo",
    "celta de vigo": "celta vigo",
    "la coruna": "deportivo la coruna",
    "rc deportivo la coruna": "deportivo la coruna",
    "vallecano": "rayo vallecano",
    "sp gijon": "sporting gijon",
    "bayern munich": "bayern munich",
    "bayern munchen": "bayern munich",
    "fc bayern munchen": "bayern munich",
    "leverkusen": "bayer leverkusen",
    "bayer 04 leverkusen": "bayer leverkusen",
    "dortmund": "borussia dortmund",
    "m'gladbach": "borussia monchengladbach",
    "borussia mgladbach": "borussia monchengladbach",
    "ein frankfurt": "eintracht frankfurt",
    "fc koln": "koln",
    "1. fc koln": "koln",
    "fc heidenheim": "heidenheim",
    "1. fc heidenheim": "heidenheim",
    "fc union berlin": "union berlin",
    "1. fc union berlin": "union berlin",
    "tsg hoffenheim": "hoffenheim",
    "tsg 1899 hoffenheim": "hoffenheim",
    "sv werder bremen": "werder bremen",
    "vfl bochum": "bochum",
    "vfl bochum 1848": "bochum",
    "vfb stuttgart": "stuttgart",
    "vfl wolfsburg": "wolfsburg",
    "sc freiburg": "freiburg",
    "sport-club freiburg": "freiburg",
    "fsv mainz 05": "mainz",
    "mainz 05": "mainz",
    "1. fsv mainz 05": "mainz",
    "rb leipzig": "leipzig",
    "rasenballsport leipzig": "leipzig",
    "fc augsburg": "augsburg",
    "sv darmstadt 98": "darmstadt",
    "darmstadt 98": "darmstadt",
}


def normalize_entity(name: str) -> str:
    """Canonical key for a team/player name: casefold, strip accents, alias."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.lower().replace(".", " ").replace("-", " ").split())
    return TEAM_ALIASES.get(text, text)


# --------------------------------------------------------------------------- #
# Match resolution — the same fixture across providers
# --------------------------------------------------------------------------- #
def match_key(record: dict) -> tuple:
    """Identity of a fixture: (date, home_key, away_key)."""
    return (
        record.get("date") or "",
        normalize_entity(record.get("home") or ""),
        normalize_entity(record.get("away") or ""),
    )


def resolve_matches(sources: dict) -> list:
    """Group records that describe the same fixture across sources.

    ``sources``: {source_name: [record, ...]} where each record has at least
    ``date`` (ISO yyyy-mm-dd), ``home``, ``away``. Returns a list of
    ``{"key": (date, home, away), "records": {source_name: record}}`` for every
    fixture seen in at least one source. Dates must match exactly — providers
    disagreeing on the calendar day is itself a conflict worth surfacing, so we
    do not paper over it silently.
    """
    grouped: dict = defaultdict(dict)
    for source_name, records in sources.items():
        for record in records:
            grouped[match_key(record)][source_name] = record
    return [
        {"key": key, "records": recs}
        for key, recs in sorted(grouped.items())
    ]


# --------------------------------------------------------------------------- #
# Field comparison + weighted fusion
# --------------------------------------------------------------------------- #
def fuse_field(values_by_source: dict, priors: dict, tolerance: float = 0.0) -> dict:
    """Fuse one field's values from multiple sources into a single value.

    Weighted vote by source prior (default 1.0). Numeric values within
    ``tolerance`` of each other count as agreeing (the mean of the agreeing
    cluster is reported). Returns ``{value, confidence, agreed, sources,
    dissent}`` — confidence is the winning cluster's share of total prior
    weight, so full agreement -> 1.0 and a 2-source split -> the larger prior's
    share. Deterministic tie-break: the cluster containing the highest-prior
    source, then lexicographic.
    """
    items = [(s, v) for s, v in sorted(values_by_source.items()) if v is not None]
    if not items:
        return {"value": None, "confidence": 0.0, "agreed": False,
                "sources": [], "dissent": {}}

    # Cluster values that agree (within tolerance for numerics).
    clusters: list = []  # each: {"value": representative, "members": [(src, val)]}
    for source, value in items:
        placed = False
        for cluster in clusters:
            ref = cluster["members"][0][1]
            same = (
                abs(value - ref) <= tolerance
                if isinstance(value, (int, float)) and isinstance(ref, (int, float))
                else value == ref
            )
            if same:
                cluster["members"].append((source, value))
                placed = True
                break
        if not placed:
            clusters.append({"members": [(source, value)]})

    def weight(cluster):
        return sum(priors.get(s, 1.0) for s, _ in cluster["members"])

    def tiebreak(cluster):
        return (max(priors.get(s, 1.0) for s, _ in cluster["members"]),
                tuple(sorted(s for s, _ in cluster["members"])))

    total = sum(weight(c) for c in clusters)
    winner = max(clusters, key=lambda c: (weight(c), tiebreak(c)))
    values = [v for _, v in winner["members"]]
    fused = (sum(values) / len(values)
             if all(isinstance(v, (int, float)) for v in values) else values[0])
    dissent = {
        s: v for c in clusters if c is not winner for s, v in c["members"]
    }
    return {
        "value": fused,
        "confidence": round(weight(winner) / total, 3) if total else 0.0,
        "agreed": len(clusters) == 1,
        "sources": [s for s, _ in winner["members"]],
        "dissent": dissent,
    }


def fuse_match(records: dict, fields: dict, priors: dict | None = None) -> dict:
    """Fuse one fixture's records into a unified record.

    ``fields``: {field_name: tolerance} — the fields to reconcile.
    Returns {field: fuse_field(...)} plus ``_conflicts`` (fields where sources
    disagreed beyond tolerance) and ``_sources`` (who contributed).
    """
    priors = priors or {}
    unified = {}
    conflicts = []
    for field, tolerance in fields.items():
        values = {s: r.get(field) for s, r in records.items()}
        fused = fuse_field(values, priors, tolerance)
        unified[field] = fused
        if fused["sources"] and not fused["agreed"]:
            conflicts.append(field)
    unified["_conflicts"] = conflicts
    unified["_sources"] = sorted(records)
    return unified


def agreement_report(resolved: list, fields: dict, priors: dict | None = None) -> dict:
    """Measured cross-source agreement per field over resolved fixtures.

    Returns {field: {"compared": n, "agreed": n, "rate": r}} counting only
    fixtures where 2+ sources supplied the field — the empirical basis for
    per-source reliability scores as more sources join.
    """
    stats: dict = {f: {"compared": 0, "agreed": 0} for f in fields}
    for fixture in resolved:
        if len(fixture["records"]) < 2:
            continue
        fused = fuse_match(fixture["records"], fields, priors)
        for field in fields:
            cell = fused[field]
            if len(cell["sources"]) + len(cell["dissent"]) >= 2:
                stats[field]["compared"] += 1
                stats[field]["agreed"] += cell["agreed"]
    return {
        f: {**v, "rate": round(v["agreed"] / v["compared"], 3) if v["compared"] else None}
        for f, v in stats.items()
    }
