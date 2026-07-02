"""Plugin system (Inference layer) — registry, discovery, isolation."""

from __future__ import annotations

import pathlib

import pytest

from fie.events import Event
from fie.plugins import clear, load_plugins, match_metric, registered, run_all
from fie.prediction import Params

PLUGINS_DIR = pathlib.Path(__file__).parent.parent / "plugins"


@pytest.fixture(autouse=True)
def clean_registry():
    clear()
    yield
    clear()


def test_register_and_run():
    @match_metric("always_half", "test metric")
    def _plugin(events, params):
        return {"value": 0.5, "summary": f"{len(events)} events seen"}

    assert "always_half" in registered()
    out = run_all([Event("m", 10, "HOME", "shot")], Params())
    assert out["always_half"]["value"] == 0.5
    assert "1 events seen" in out["always_half"]["summary"]


def test_broken_plugin_is_isolated():
    @match_metric("boom", "explodes")
    def _bad(events, params):
        raise RuntimeError("kaput")

    @match_metric("fine", "works")
    def _good(events, params):
        return {"value": 1.0, "summary": "ok"}

    out = run_all([], Params())
    assert out["boom"]["error"] == "kaput"      # reported, not raised
    assert out["fine"]["value"] == 1.0          # neighbours unaffected


def test_discovery_loads_expected_chaos():
    names = load_plugins(PLUGINS_DIR)
    assert "expected_chaos" in names
    events = [
        Event("m", 10, "HOME", "goal"), Event("m", 40, "AWAY", "goal"),
        Event("m", 60, "AWAY", "goal"), Event("m", 88, "HOME", "goal"),
        Event("m", 90, "HOME", "goal"), Event("m", 70, "AWAY", "red_card"),
    ]
    out = run_all(events, Params())
    chaos = out["expected_chaos"]
    assert 0.0 <= chaos["value"] <= 1.0
    assert chaos["components"]["lead_changes"] >= 2   # HOME -> AWAY -> HOME
    assert chaos["components"]["late_goals"] == 2
    assert "summary" in chaos


def test_quiet_match_scores_low_chaos():
    load_plugins(PLUGINS_DIR)
    quiet = [Event("m", 30, "HOME", "shot"), Event("m", 60, "AWAY", "corner")]
    wild_events = [
        Event("m", m, "HOME" if i % 2 else "AWAY", "goal")
        for i, m in enumerate((10, 25, 50, 81, 86, 90))
    ] + [Event("m", 70, "HOME", "red_card")]
    quiet_v = run_all(quiet, Params())["expected_chaos"]["value"]
    wild_v = run_all(wild_events, Params())["expected_chaos"]["value"]
    assert quiet_v < 0.3 < wild_v
