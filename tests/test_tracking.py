"""Reference tracking connector — interoperability at the ingestion boundary."""

from __future__ import annotations

import json
import pathlib

from fie.sources.tracking import (
    TrackingConnector,
    parse_csv,
    parse_json,
    to_canonical_records,
    to_vision_items,
)
from fie.vision import estimate_positions

SAMPLE = (pathlib.Path(__file__).parent.parent / "examples" / "tracking_sample.csv").read_text()


def test_parse_csv_normalizes_frames():
    frames = parse_csv(SAMPLE)
    assert frames[0] == {"t": 0.0, "player_id": "1", "team": "HOME",
                         "x": 50.0, "y": 50.0, "player": "Alice Keeper"}
    # Deterministic order: by time then player.
    assert [f["t"] for f in frames] == sorted(f["t"] for f in frames)
    assert {f["player_id"] for f in frames} == {"1", "2", "3"}


def test_parse_csv_skips_malformed_rows_without_guessing():
    text = "t,player_id,team,x,y\n0.0,1,HOME,10,20\n0.1,2,HOME,,30\nbad,3,AWAY,1,2\n"
    frames = parse_csv(text)
    assert len(frames) == 1 and frames[0]["player_id"] == "1"


def test_json_and_csv_agree():
    frames = parse_csv(SAMPLE)
    as_json = json.dumps({"frames": frames})
    assert parse_json(as_json) == frames


def test_frames_feed_the_vision_engine():
    # The whole point: a tracking feed flows straight into the continuous state
    # estimator the Digital Twin already uses.
    items = to_vision_items(parse_csv(SAMPLE))
    state = estimate_positions(items, at_seconds=0.08)
    assert set(state) == {"1", "2", "3"}
    assert abs(state["2"]["x"] - 31.6) < 0.5          # Bob near his 0.08 position
    assert all(0.0 <= e["confidence"] <= 1.0 for e in state.values())


def test_frames_lift_into_the_canonical_pipeline():
    from fie.canonical import canonical_player_id, stage_of, Stage
    from fie.fusiondata import Layer

    recs = to_canonical_records(parse_csv(SAMPLE)[:3], match_id="m1",
                                source="optical-x", collected_at="2026-01-01")
    assert len(recs) == 3
    r = recs[0]
    assert r.kind == "position" and r.layer is Layer.OBSERVED
    assert stage_of(r) is Stage.CANONICAL
    assert r.provenance.source == "optical-x"          # traceable to the provider
    # Source-agnostic FUT-K id (from the display name here).
    assert r.context.player_id == canonical_player_id("Alice Keeper")


def test_connector_surface_and_determinism():
    c = TrackingConnector(name="second-spectrum", base_trust=0.95)
    a = c.vision_items(SAMPLE)
    b = c.vision_items(SAMPLE)
    assert a == b and a[0]["type"] == "tracking"
    assert c.name == "second-spectrum" and c.base_trust == 0.95
