"""Explanatory Intelligence (Section 19).

The AI never answers just ``72%``. It assembles the *why* from the modules already
built: the change detector says something shifted, causality says why, spatial and
tactical name the mechanism, the individual layer names the players, and the
confidence engine tunes how firmly each clause is stated.
"""

from __future__ import annotations

# Above this confidence, causal claims are stated plainly; at or below it they are
# hedged (Section 19 / the panel design of Section 22).
CONFIDENCE_HEDGE_THRESHOLD = 0.66


def explain(prediction, change, causes, mechanisms, drivers, confidence) -> dict:
    """Assemble an explanation for ``prediction`` from its supporting evidence."""
    lines = []
    if change:
        lines.append(f"the game shifted at minute {change['minute']}")
    lines += [f"✓ {m}" for m in mechanisms]
    lines += [f"✓ {c}" for c in causes]
    lines += [f"✓ {d}" for d in drivers]
    hedge = "" if confidence > CONFIDENCE_HEDGE_THRESHOLD else " (tentative — low confidence)"
    return {"claim": prediction, "because": lines, "note": hedge}
