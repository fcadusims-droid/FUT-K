"""Knowledge Graph over the canonical store (Inference).

The knowledge_records store is flat: each datum carries a rich context but the
*relations* between entities are implicit. This module makes them explicit — a
queryable graph of the football ecosystem (player ↔ team ↔ match ↔ competition)
derived **deterministically** from each record's context, with every edge
carrying its temporal validity and provenance. It is the Knowledge-stage of the
Dataset Fusion pipeline (docs/design/LONG_TERM_VISION.md, readiness item 2).

Pure and deterministic: same records, same graph, same query answers. It reads
only the canonical contract (``fie.fusiondata``); it invents no relation the data
does not already imply, and it never mixes across the boundaries the isolation
contract protects — an edge exists only because a real record's context put those
two entities together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Node:
    """One entity in the graph: a player, team, match or competition."""

    type: str   # "player" | "team" | "match" | "competition"
    id: str

    @property
    def key(self) -> str:
        return f"{self.type}:{self.id}"


# The relations derived from a record's context. Each rule fires only when both
# endpoints are present, so an edge is always backed by real context.
def _edges_from_context(ctx) -> list:
    p = Node("player", ctx.player_id) if ctx.player_id else None
    t = Node("team", ctx.team) if ctx.team else None
    m = Node("match", ctx.match_id) if ctx.match_id else None
    c = Node("competition", ctx.competition) if ctx.competition else None
    home = Node("team", ctx.home) if ctx.home else None
    away = Node("team", ctx.away) if ctx.away else None
    edges = []
    if p and m:
        edges.append((p, "appeared_in", m))
    if p and t:
        edges.append((p, "played_for", t))
    if t and m:
        edges.append((t, "competed_in", m))
    if m and c:
        edges.append((m, "part_of", c))
    if p and c:
        edges.append((p, "active_in", c))
    if home and away:
        edges.append((home, "faced", away))
    return edges


def _widen(a: Optional[str], b: Optional[str], *, latest: bool) -> Optional[str]:
    """Combine two validity bounds, keeping the widest window (None = unbounded)."""
    if a is None or b is None:
        return None
    return max(a, b) if latest else min(a, b)


@dataclass
class Edge:
    """A relation between two nodes, aggregated over the records that back it."""

    source: str        # node key
    relation: str
    target: str        # node key
    count: int = 0
    sources: set = field(default_factory=set)   # provenance sources
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source, "relation": self.relation, "target": self.target,
            "count": self.count, "sources": sorted(self.sources),
            "valid_from": self.valid_from, "valid_to": self.valid_to,
        }


def _active_at(edge: Edge, at: str) -> bool:
    if edge.valid_from is not None and at < edge.valid_from:
        return False
    if edge.valid_to is not None and at >= edge.valid_to:
        return False
    return True


class KnowledgeGraph:
    """A deterministic, queryable graph built from KnowledgeRecords."""

    def __init__(self) -> None:
        self.nodes: dict = {}                      # key -> Node
        self.edges: dict = {}                      # (src, rel, dst) -> Edge
        self._adj: dict = {}                       # node key -> set of edge keys

    # -- construction ------------------------------------------------------- #
    def add_record(self, record) -> None:
        source = record.provenance.source
        vf, vt = record.temporal.valid_from, record.temporal.valid_to
        for src, rel, dst in _edges_from_context(record.context):
            self.nodes.setdefault(src.key, src)
            self.nodes.setdefault(dst.key, dst)
            ekey = (src.key, rel, dst.key)
            edge = self.edges.get(ekey)
            if edge is None:
                edge = Edge(source=src.key, relation=rel, target=dst.key,
                            valid_from=vf, valid_to=vt)
                self.edges[ekey] = edge
                self._adj.setdefault(src.key, set()).add(ekey)
                self._adj.setdefault(dst.key, set()).add(ekey)
            else:
                edge.valid_from = _widen(edge.valid_from, vf, latest=False)
                edge.valid_to = _widen(edge.valid_to, vt, latest=True)
            edge.count += 1
            if source:
                edge.sources.add(source)

    # -- queries ------------------------------------------------------------ #
    def nodes_of_type(self, node_type: str) -> list:
        return sorted((n for n in self.nodes.values() if n.type == node_type),
                      key=lambda n: n.id)

    def relations(self, node_key: str, *, as_of: Optional[str] = None) -> list:
        """Every edge touching ``node_key`` (optionally valid on ``as_of``)."""
        out = [self.edges[k] for k in self._adj.get(node_key, ())]
        if as_of is not None:
            out = [e for e in out if _active_at(e, as_of)]
        return sorted(out, key=lambda e: (-e.count, e.source, e.relation, e.target))

    def neighbors(self, node_key: str, *, relation: Optional[str] = None,
                  as_of: Optional[str] = None) -> list:
        """Nodes directly related to ``node_key`` (filtered by relation/time)."""
        seen: dict = {}
        for e in self.relations(node_key, as_of=as_of):
            if relation is not None and e.relation != relation:
                continue
            other = e.target if e.source == node_key else e.source
            direction = "out" if e.source == node_key else "in"
            seen.setdefault(other, {"node": self.nodes[other].__dict__ | {"key": other},
                                    "relation": e.relation, "direction": direction,
                                    "count": e.count})
        return list(seen.values())

    def to_dict(self, *, limit: Optional[int] = None) -> dict:
        edges = sorted(self.edges.values(),
                       key=lambda e: (-e.count, e.source, e.relation, e.target))
        if limit is not None:
            edges = edges[:limit]
        node_keys = {e.source for e in edges} | {e.target for e in edges}
        return {
            "nodes": [self.nodes[k].__dict__ | {"key": k} for k in sorted(node_keys)],
            "edges": [e.to_dict() for e in edges],
            "n_nodes": len(self.nodes),
            "n_edges": len(self.edges),
        }


def build_graph(records) -> KnowledgeGraph:
    """Build the knowledge graph from an iterable of KnowledgeRecords."""
    g = KnowledgeGraph()
    for record in records:
        g.add_record(record)
    return g
