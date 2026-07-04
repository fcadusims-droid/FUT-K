"""football-data.org connector (Layer 1) — offline mapping tests.

Exercises the v4 -> normalized ``Event`` mapping against a fixture with the real
provider schema. No network: the HTTP loader is injected. A separate, network-
gated smoke (``test_footballdata_live.py``) hits the real keyless API.
"""

from __future__ import annotations

import json
import pathlib

from fie.sources.footballdata import (
    FootballDataSource,
    current_minute,
    events_from_match,
    observations_from_match,
    team_side,
)

MATCH = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "footballdata_match.json").read_text()
)


def test_goals_mapped_with_side_and_minute():
    events = events_from_match(MATCH)
    goals = [e for e in events if e.type == "goal"]
    assert [(e.minute, e.team) for e in goals] == [(12.0, "HOME"), (58.0, "AWAY"), (83.0, "HOME")]
    assert goals[0].player_id == "7801"  # the provider's scorer id, not invented


def test_cards_mapped_yellow_and_second_yellow_to_red():
    events = events_from_match(MATCH)
    cards = [e for e in events if e.type in ("yellow_card", "red_card")]
    assert (cards[0].minute, cards[0].type, cards[0].team) == (34.0, "yellow_card", "AWAY")
    # YELLOW_RED (a second yellow) becomes a red_card — a sending-off.
    assert (cards[1].minute, cards[1].type, cards[1].team) == (77.0, "red_card", "AWAY")


def test_substitution_uses_player_in_and_is_sorted():
    events = events_from_match(MATCH)
    assert [e.minute for e in events] == sorted(e.minute for e in events)  # chronological
    sub = next(e for e in events if e.type == "substitution")
    assert sub.minute == 65.0 and sub.team == "HOME"
    assert sub.player_id == "7821"  # playerIn


def test_total_events_and_no_fabrication():
    # exactly 3 goals + 2 cards + 1 sub = 6; nothing else is emitted.
    assert len(events_from_match(MATCH)) == 6


def test_team_side_by_id_and_name_and_unknown():
    assert team_side(MATCH, {"id": 1766}) == "HOME"
    assert team_side(MATCH, {"id": 1783}) == "AWAY"
    assert team_side(MATCH, {"name": "CR Flamengo"}) == "HOME"      # name fallback
    assert team_side(MATCH, {"id": 999, "name": "Other FC"}) is None  # neither side


def test_unresolvable_team_event_is_dropped():
    match = {"id": 1, "homeTeam": {"id": 10}, "awayTeam": {"id": 20},
             "goals": [{"minute": 5, "team": {"id": 999}, "scorer": {"id": 1}}]}
    assert events_from_match(match) == []  # dropped, never guessed to a side


def test_current_minute_prefers_live_clock():
    assert current_minute({**MATCH, "minute": 67}) == 67.0
    assert current_minute(MATCH) == 83.0            # finished: falls back to last event
    assert current_minute({"id": 1}) == 0.0         # nothing known


def test_observations_shape_for_live_mode():
    obs = observations_from_match(MATCH)
    assert all(set(o) == {"minute", "team", "type", "player_id"} for o in obs)
    assert all(o["team"] in ("HOME", "AWAY") for o in obs)


def test_source_stream_and_wrappers_via_injected_loader():
    routes = {
        "https://api.football-data.org/v4/matches/500001": {"match": MATCH},
        "https://api.football-data.org/v4/competitions": {"competitions": [{"code": "BSA"}]},
        "https://api.football-data.org/v4/matches": {"matches": [{"id": 7, "status": "IN_PLAY"}]},
    }
    src = FootballDataSource(http_get=lambda url: routes[url])
    assert src.name == "football-data.org" and 0.0 <= src.base_trust <= 1.0
    assert [e.type for e in src.stream("500001")].count("goal") == 3
    assert src.competitions() == [{"code": "BSA"}]
    assert src.live_matches()[0]["status"] == "IN_PLAY"
