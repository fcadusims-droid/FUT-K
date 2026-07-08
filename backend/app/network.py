"""Passing-network builder + store (the ingestion boundary for networks).

This is the *only* backend serving-adjacent module allowed to read raw provider
events, exactly like ``twin.py``: it derives a team's passing network from the
raw event cache, stores it as a canonical ``PassingNetworkRow``, and hands the
``/network`` endpoint a payload from that store. The endpoint itself never touches
a provider — it depends on the canonical dataset (the Dataset Fusion boundary
rule, enforced by ``tests/test_data_boundary.py``).

``network_payload`` stays a pure function of raw-shaped events, so it is fully
testable offline.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fie.players import critical_links, passing_network
from fie.sources.statsbomb import passing_records
from fie.tactical import dependence_on_key_players, team_robustness

from .models import Match, PassingNetworkRow

# Repo-root .sb_cache by default; override with SB_CACHE.
DEFAULT_CACHE = os.environ.get(
    "SB_CACHE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".sb_cache"),
)

MAX_EDGES = 30


def _short(name: str) -> str:
    parts = (name or "").split()
    return parts[-1] if parts else name


def network_payload(raw_events: list, team_name: str) -> dict:
    """Graph payload: nodes (by involvement) + strongest edges + team metrics."""
    names: dict = {}
    graph = passing_network(passing_records(raw_events, team_name, names))
    if not graph:
        return {"team": team_name, "nodes": [], "edges": [], "robustness": 0.0,
                "dependence": 0.0}

    strength: dict = {}
    for (a, b), d in graph.items():
        strength[a] = strength.get(a, 0) + d["weight"]
        strength[b] = strength.get(b, 0) + d["weight"]

    central = set(critical_links(graph, top=11))  # a starting XI's worth
    nodes = [
        {"id": pid, "name": names.get(pid, pid), "label": _short(names.get(pid, pid)),
         "strength": strength[pid]}
        for pid in sorted(central, key=lambda p: -strength[p])
    ]
    node_ids = {n["id"] for n in nodes}
    edges = sorted(
        (
            {"from": a, "to": b, "passes": d["weight"], "chances": d["chances"]}
            for (a, b), d in graph.items()
            if a in node_ids and b in node_ids
        ),
        key=lambda e: -e["passes"],
    )[:MAX_EDGES]

    return {
        "team": team_name,
        "nodes": nodes,
        "edges": edges,
        "robustness": round(team_robustness(graph), 3),
        "dependence": round(dependence_on_key_players(graph), 3),
    }


def _team_for_side(match: Match, side: str) -> str:
    return (match.home_team if side == "HOME" else match.away_team) or side


def build_network(session: Session, match: Match, side: str,
                  cache_dir: str = DEFAULT_CACHE) -> PassingNetworkRow | None:
    """Build + persist one team's passing network from the raw event cache.

    Returns None when the raw events file is unavailable (the endpoint then
    reports the network cannot be built — honest degradation, no guessing).
    """
    path = os.path.join(cache_dir, f"events_{match.id}.json")
    if not os.path.exists(path):
        return None
    raw_events = json.load(open(path, encoding="utf-8"))
    payload = network_payload(raw_events, _team_for_side(match, side))
    payload["side"] = side
    row = PassingNetworkRow(
        match_id=match.id, side=side,
        payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    session.merge(row)
    session.commit()
    return row


def get_network(session: Session, match: Match, side: str,
                cache_dir: str = DEFAULT_CACHE) -> dict | None:
    """Stored network, or build-on-first-request when the raw cache allows it."""
    row = session.get(PassingNetworkRow, (match.id, side))
    if row is None:
        row = build_network(session, match, side, cache_dir)
    if row is None:
        return None
    return json.loads(row.payload)
