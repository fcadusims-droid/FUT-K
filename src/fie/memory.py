"""Match Memory (Section 17).

A structured, replayable timeline of how the match evolved tactically and
emotionally — not just a list of highlights.

Spec-completeness module: exercised by its numbered tests; not yet wired
into the product serving path (integration is tracked in docs/ROADMAP.md).
"""

from __future__ import annotations


def remember(timeline, minute: float, headline: str, detail: str = "") -> None:
    """Append one entry to the timeline without touching earlier entries."""
    timeline.append({"minute": minute, "headline": headline, "detail": detail})


def replay(timeline):
    """Yield the tactical/emotional story arc ordered by minute."""
    return sorted(timeline, key=lambda e: e["minute"])
