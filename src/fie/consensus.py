"""Consensus engine — evidence fusion (Section 16).

Reconciles every source into one diagnosis plus an agreement level. When sources
disagree, that disagreement is itself information.
"""

from __future__ import annotations

from collections import defaultdict


def consensus(readings) -> dict:
    """Fuse weighted source readings into ``{"claim", "agreement"}``.

    ``readings``: list of ``{"claim": ..., "weight": credibility}``. On a tie in
    total weight the claim is chosen deterministically as the lexicographically
    smallest one (documented tie-break, independent of dict/insertion order — see
    T-16-04).
    """
    tally = defaultdict(float)
    total_w = 0.0
    for r in readings:
        tally[r["claim"]] += r["weight"]
        total_w += r["weight"]
    if total_w == 0:
        return {"claim": None, "agreement": 0.0}
    best = max(tally.values())
    claim = min(c for c, w in tally.items() if w == best)
    return {"claim": claim, "agreement": tally[claim] / total_w}
