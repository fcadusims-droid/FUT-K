"""Passing-network payload for the app (Section 12, Layer 5 as product).

Builds one team's interaction graph for a single match from raw StatsBomb
events, reusing the validated engine functions. Pure function -> testable
offline; the endpoint wires it to the on-disk StatsBomb cache.
"""

from __future__ import annotations

import os

from fie.players import critical_links, passing_network
from fie.sources.statsbomb import passing_records
from fie.tactical import dependence_on_key_players, team_robustness

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
