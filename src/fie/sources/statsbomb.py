"""StatsBomb open-data connector (Layer 1).

Maps StatsBomb's free event-level open data
(https://github.com/statsbomb/open-data) onto the normalized ``Event`` model.
Standard-library only: HTTP via ``urllib`` with retries, JSON via ``json``.

Mapping decisions (documented so the tests can pin them down):
  - Shot with outcome "Goal"          -> a ``shot_on_target`` **and** a ``goal``
  - Shot "Saved" / "Saved to Post"     -> ``shot_on_target``
  - any other Shot outcome             -> ``shot``
  - Pass with pass.type "Corner"       -> ``corner``
  - Foul Committed                     -> ``foul`` (+ ``yellow_card`` / ``red_card``
                                          if it carried a card)
  - Bad Behaviour with a card          -> ``yellow_card`` / ``red_card``
Positions are rescaled from StatsBomb's 120x80 pitch to the engine's 0-100 pitch.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

from ..events import Event
from .base import Source

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

SHOT_ON_TARGET_OUTCOMES = {"Saved", "Saved to Post"}
RED_CARDS = {"Red Card", "Second Yellow"}


def _rescale(loc):
    """StatsBomb 120x80 pitch coordinates -> engine 0-100 pitch (or None)."""
    if not loc:
        return None, None
    x = loc[0] * 100.0 / 120.0 if loc[0] is not None else None
    y = loc[1] * 100.0 / 80.0 if len(loc) > 1 and loc[1] is not None else None
    return x, y


def _map_one(raw, team, minute, x, y, player_id, match_id):
    """Map one StatsBomb event to zero-or-more normalized Events."""
    etype = raw.get("type", {}).get("name")

    def ev(t, xg=None):
        return Event(match_id=match_id, minute=minute, team=team, type=t,
                     player_id=player_id, x=x, y=y, xg=xg)

    if etype == "Shot":
        shot = raw.get("shot", {})
        outcome = shot.get("outcome", {}).get("name")
        xg = shot.get("statsbomb_xg")
        if outcome == "Goal":
            return [ev("shot_on_target", xg), ev("goal", xg)]
        if outcome in SHOT_ON_TARGET_OUTCOMES:
            return [ev("shot_on_target", xg)]
        return [ev("shot", xg)]

    if etype == "Pass" and raw.get("pass", {}).get("type", {}).get("name") == "Corner":
        return [ev("corner")]

    if etype == "Foul Committed":
        out = [ev("foul")]
        card = raw.get("foul_committed", {}).get("card", {}).get("name")
        if card in RED_CARDS:
            out.append(ev("red_card"))
        elif card == "Yellow Card":
            out.append(ev("yellow_card"))
        return out

    if etype == "Bad Behaviour":
        card = raw.get("bad_behaviour", {}).get("card", {}).get("name")
        if card in RED_CARDS:
            return [ev("red_card")]
        if card == "Yellow Card":
            return [ev("yellow_card")]

    return []


def events_from_statsbomb(raw_events, home_team, away_team, match_id):
    """Convert a StatsBomb event array into sorted normalized ``Event`` objects."""
    out = []
    for raw in raw_events:
        team_name = raw.get("team", {}).get("name")
        if team_name == home_team:
            team = "HOME"
        elif team_name == away_team:
            team = "AWAY"
        else:
            continue
        minute = float(raw.get("minute", 0)) + float(raw.get("second", 0)) / 60.0
        x, y = _rescale(raw.get("location"))
        player = raw.get("player") or {}
        player_id = str(player["id"]) if player.get("id") is not None else None
        out.extend(_map_one(raw, team, minute, x, y, player_id, match_id))
    out.sort(key=lambda e: e.minute)
    return out


def match_dict_from_statsbomb(raw_match, raw_events):
    """Build a backtest-ready match dict from a StatsBomb match + its events."""
    match_id = str(raw_match["match_id"])
    home = raw_match["home_team"]["home_team_name"]
    away = raw_match["away_team"]["away_team_name"]
    events = events_from_statsbomb(raw_events, home, away, match_id)
    duration = int(max((e.minute for e in events), default=90)) + 1
    return {
        "match_id": match_id,
        "home_team": home,
        "away_team": away,
        "home_score": raw_match.get("home_score"),
        "away_score": raw_match.get("away_score"),
        "events": events,
        "duration": duration,
    }


# --------------------------------------------------------------------------- #
# Live download helpers (used by the ingestion script, never by CI tests)
# --------------------------------------------------------------------------- #
def _get_json(url, retries=4, timeout=90):
    """GET + parse JSON, retrying on transient errors / truncated responses."""
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001 - includes truncated-read JSON errors
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last


def fetch_competitions():
    return _get_json(f"{BASE_URL}/competitions.json")


def fetch_matches(competition_id, season_id):
    return _get_json(f"{BASE_URL}/matches/{competition_id}/{season_id}.json")


def fetch_events(match_id, cache_dir=None):
    """Fetch a match's events, using a local cache directory when provided."""
    cache_path = None
    if cache_dir:
        cache_path = os.path.join(cache_dir, f"events_{match_id}.json")
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as fh:
                return json.load(fh)
    data = _get_json(f"{BASE_URL}/events/{match_id}.json")
    if cache_path:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    return data


class StatsBombSource(Source):
    """A pluggable ``Source`` over StatsBomb open data (post-match replay)."""

    name = "statsbomb"
    base_trust = 0.95  # curated, high-quality event data

    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir

    def stream(self, match_id):
        raw_match, raw_events = self._load(match_id)
        yield from match_dict_from_statsbomb(raw_match, raw_events)["events"]

    def _load(self, match_id):  # pragma: no cover - network path
        raise NotImplementedError(
            "StatsBombSource.stream needs the match metadata; use "
            "match_dict_from_statsbomb() with fetch_matches()/fetch_events() in the "
            "ingestion script."
        )
