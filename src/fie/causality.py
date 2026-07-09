"""Causality Model (Section 18).

When a hypothesis is confirmed, look for likely causes in the match itself. Causes
are read from objective indicators, each with a documented trigger — explanatory
hypotheses, not proven causation.

Spec-completeness module: exercised by its numbered tests; not yet wired
into the product serving path (integration is tracked in docs/ROADMAP.md).
"""

from __future__ import annotations


def likely_causes(features: dict):
    """Return the causes whose triggers fire, in a fixed, documented order.

    Boundary rule (T-18-04): ``passes_received_rel`` uses a strict ``<`` — a value
    of exactly 0.7 does *not* trigger. ``nearby_markers`` uses ``>=``.
    """
    causes = []
    if features.get("passes_received_rel", 1.0) < 0.7:
        causes.append("receiving fewer passes than usual")
    if features.get("nearby_markers", 0) >= 2:
        causes.append("closely marked by 2+ defenders")
    if features.get("changed_zone", False):
        causes.append("moved to a different zone")
    if features.get("team_midfield_control", 1.0) < 0.4:
        causes.append("the team lost control of midfield")
    return causes
