"""Reference tracking connector — a positional feed at the ingestion boundary.

The Dataset Fusion's interoperability promise made concrete (readiness item 3):
an institution can plug a **tracking / positional feed** into FUT-K through one
small, open connector, and every downstream module (the Vision Engine, tactics,
the twin) consumes it without knowing the provider — the same source-agnostic
rule that already governs event data.

A positional connector is the sibling of the on-ball ``Source`` (``base.py``):
on-ball sources emit ``Event``s; a positional source emits **frames** — a
player's ``(t, x, y)`` sampled densely over time. This reference implementation
parses an **open CSV/JSON format** (7 fields, like the custom-events path), so it
needs no proprietary SDK; a real Opta/second-spectrum/optical feed implements the
same tiny surface. It also shows the full pipeline: raw rows → normalized frames →
canonical records / Vision-Engine items.

Pure and deterministic; standard library only (``csv``, ``json``). No network —
the ingestion script (Application) hands it the provider's bytes.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

# The open tracking format's fields. ``player`` (display name) is optional; a
# provider that ships only ids simply omits it.
FIELDS = ("t", "player_id", "team", "x", "y", "player")


def _frame(t, player_id, team, x, y, player=None) -> dict:
    """One normalized tracking frame (a player's position at an instant)."""
    return {
        "t": float(t), "player_id": str(player_id),
        "team": team, "x": float(x), "y": float(y),
        "player": player or None,
    }


def parse_csv(text: str) -> list:
    """Parse the open CSV tracking format into normalized frames.

    Columns: ``t,player_id,team,x,y[,player]`` (header required; extra columns
    ignored). Rows missing a required field are skipped, never guessed.
    """
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out.append(_frame(row["t"], row["player_id"], row.get("team"),
                              row["x"], row["y"], row.get("player")))
        except (KeyError, ValueError, TypeError):
            continue
    return _sorted(out)


def parse_json(text: str) -> list:
    """Parse the open JSON tracking format: a list of frame objects."""
    doc = json.loads(text)
    frames = doc.get("frames") if isinstance(doc, dict) else doc
    out = []
    for f in frames or []:
        try:
            out.append(_frame(f["t"], f["player_id"], f.get("team"),
                              f["x"], f["y"], f.get("player")))
        except (KeyError, ValueError, TypeError):
            continue
    return _sorted(out)


def _sorted(frames: list) -> list:
    """Deterministic order: by time, then player — the vision stream's order."""
    return sorted(frames, key=lambda f: (f["t"], f["player_id"]))


def to_vision_items(frames: list) -> list:
    """Frames in the shape the Vision Engine consumes (``fie.vision``).

    The Vision Engine reads ``{t, x, y, player_id, player}`` — so a tracking feed
    flows straight into the continuous state estimator the Digital Twin already
    uses, which is exactly why the real-time-CV vision only needs this *producer*:
    the consumer is already built and validated.
    """
    return [
        {"t": f["t"], "x": f["x"], "y": f["y"], "player_id": f["player_id"],
         "player": f["player"], "team": f["team"], "type": "tracking"}
        for f in frames
    ]


def to_canonical_records(frames: list, *, match_id: str, source: str,
                         collected_at: Optional[str] = None) -> list:
    """Lift frames into canonical OBSERVED position records (Raw → Canonical).

    Each frame becomes one ``position`` record with FUT-K's own ids and full
    provenance, so a tracking provider enters the store under the exact same
    contract as every other source — nothing downstream depends on which optical
    system produced it.
    """
    from fie.canonical import canonical_player_id, canonical_record
    from fie.fusiondata import Context

    out = []
    for f in frames:
        pid = canonical_player_id(f["player"] or f["player_id"])
        context = Context(match_id=match_id, player_id=pid, team=f["team"],
                          second=f["t"])
        out.append(canonical_record(
            "position", {"x": f["x"], "y": f["y"], "t": f["t"]},
            context=context, source=source, collected_at=collected_at))
    return out


class TrackingConnector:
    """A positional source: parse a provider's bytes into normalized frames.

    The tiny surface a tracking provider implements — mirror it for Opta,
    Second Spectrum, an optical-tracking export, or a computer-vision pipeline;
    the rest of FUT-K never changes.
    """

    def __init__(self, name: str = "tracking", base_trust: float = 0.9) -> None:
        self.name = name
        self.base_trust = base_trust

    def frames(self, text: str, fmt: str = "csv") -> list:
        return parse_json(text) if fmt == "json" else parse_csv(text)

    def vision_items(self, text: str, fmt: str = "csv") -> list:
        return to_vision_items(self.frames(text, fmt))
