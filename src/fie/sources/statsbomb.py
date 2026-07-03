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
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from ..events import Event
from .base import Source

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


@dataclass
class PassRecord:
    """One pass for the interaction network (Section 12, Layer 5)."""

    from_: str
    to: Optional[str]
    success: bool
    created_chance: bool

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


# On-ball action types that count toward a player's involvement volume.
ONBALL_TYPES = {"Pass", "Shot", "Dribble", "Carry"}


def passing_records(raw_events, team_name, names=None):
    """Extract ``PassRecord`` objects for ``team_name`` (Section 12, Layer 5).

    Feeds ``players.passing_network``. Successful passes are completed passes
    (StatsBomb marks only failures with an outcome) that have a recipient; a pass
    "creates a chance" if it set up a shot or a goal. ``names`` (optional dict) is
    filled with player_id -> name for reporting.
    """
    records = []
    for e in raw_events:
        if e.get("type", {}).get("name") != "Pass":
            continue
        if e.get("team", {}).get("name") != team_name:
            continue
        pinfo = e.get("pass", {})
        passer = e.get("player") or {}
        recipient = pinfo.get("recipient") or {}
        pid = passer.get("id")
        rid = recipient.get("id")
        if pid is None:
            continue
        success = "outcome" not in pinfo and rid is not None
        created = bool(pinfo.get("shot_assist") or pinfo.get("goal_assist"))
        records.append(
            PassRecord(str(pid), str(rid) if rid is not None else None, success, created)
        )
        if names is not None:
            if passer.get("name"):
                names[str(pid)] = passer["name"]
            if rid is not None and recipient.get("name"):
                names[str(rid)] = recipient["name"]
    return records


def accumulate_player_stats(raw_events, home_team, away_team, table=None):
    """Accumulate per-player counters (Section 12) from a match's raw events.

    Updates ``table`` (``{player_id: record}``) in place across matches so a whole
    competition's DNA can be built by calling this once per match.
    """
    from ..profiling import new_record  # local import avoids a cycle at module load

    table = table if table is not None else {}
    for e in raw_events:
        player = e.get("player") or {}
        pid = player.get("id")
        if pid is None:
            continue
        team_name = e.get("team", {}).get("name")
        if team_name == home_team:
            team = "HOME"
        elif team_name == away_team:
            team = "AWAY"
        else:
            continue
        rec = table.get(str(pid))
        if rec is None:
            rec = new_record(pid, player.get("name"), team, e.get("position", {}).get("name"))
            table[str(pid)] = rec

        etype = e.get("type", {}).get("name")
        if etype in ONBALL_TYPES:
            rec["actions"] += 1
        if etype == "Pass":
            pinfo = e.get("pass", {})
            rec["passes"] += 1
            if "outcome" not in pinfo:  # StatsBomb: completed passes carry no outcome
                rec["passes_completed"] += 1
                loc = e.get("location")
                end = pinfo.get("end_location")
                if loc and end and (end[0] - loc[0]) >= 15.0:
                    rec["progressive"] += 1
            if pinfo.get("shot_assist"):
                rec["key_passes"] += 1
            if pinfo.get("goal_assist"):
                rec["assists"] += 1
        elif etype == "Shot":
            rec["shots"] += 1
            if e.get("shot", {}).get("outcome", {}).get("name") == "Goal":
                rec["goals"] += 1
        elif etype == "Dribble":
            rec["dribbles"] += 1
            if e.get("dribble", {}).get("outcome", {}).get("name") == "Complete":
                rec["dribbles_completed"] += 1
        elif etype in ("Dispossessed", "Miscontrol"):
            rec["turnovers"] += 1
    return table


def _event_minute(e):
    return float(e.get("minute", 0)) + float(e.get("second", 0)) / 60.0


def match_on_off(raw_events, team_name):
    """Reconstruct on-pitch intervals for one team and its goals (Layer 4).

    Returns ``{match_end, team_goals, per_player: {pid: {name, on_min, goals_on}}}``.
    Starters run from minute 0; substitutions and red cards open/close intervals;
    all open intervals close at full time (max event minute, extra time included).
    """
    match_end = max((_event_minute(e) for e in raw_events), default=90.0)
    names = {}
    starters = []
    on_at = {}
    off_at = {}

    for e in raw_events:
        etype = e.get("type", {}).get("name")
        same_team = e.get("team", {}).get("name") == team_name
        if etype == "Starting XI" and same_team:
            for slot in e.get("tactics", {}).get("lineup", []):
                p = slot.get("player", {})
                if p.get("id") is not None:
                    starters.append(str(p["id"]))
                    names[str(p["id"])] = p.get("name")
        elif etype == "Substitution" and same_team:
            minute = _event_minute(e)
            off_p = e.get("player", {})
            if off_p.get("id") is not None:
                off_at[str(off_p["id"])] = minute
                names[str(off_p["id"])] = off_p.get("name")
            repl = e.get("substitution", {}).get("replacement", {})
            if repl.get("id") is not None:
                on_at[str(repl["id"])] = minute
                names[str(repl["id"])] = repl.get("name")
        elif same_team and etype in ("Foul Committed", "Bad Behaviour"):
            card = (
                e.get("foul_committed", {}).get("card", {}).get("name")
                if etype == "Foul Committed"
                else e.get("bad_behaviour", {}).get("card", {}).get("name")
            )
            if card in RED_CARDS:
                p = e.get("player", {})
                if p.get("id") is not None:
                    off_at[str(p["id"])] = _event_minute(e)

    intervals = {}
    for pid in starters:
        intervals[pid] = (0.0, off_at.get(pid, match_end))
    for pid, minute in on_at.items():
        intervals[pid] = (minute, off_at.get(pid, match_end))

    goal_minutes = [
        _event_minute(e)
        for e in raw_events
        if e.get("type", {}).get("name") == "Shot"
        and e.get("team", {}).get("name") == team_name
        and e.get("shot", {}).get("outcome", {}).get("name") == "Goal"
    ]

    per_player = {}
    for pid, (start, end) in intervals.items():
        on_min = max(0.0, end - start)
        goals_on = sum(1 for gm in goal_minutes if start <= gm <= end)
        per_player[pid] = {"name": names.get(pid), "on_min": on_min, "goals_on": goals_on}

    return {"match_end": match_end, "team_goals": len(goal_minutes), "per_player": per_player}


def match_dict_from_statsbomb(raw_match, raw_events):
    """Build a backtest-ready match dict from a StatsBomb match + its events."""
    match_id = str(raw_match["match_id"])
    home = raw_match["home_team"]["home_team_name"]
    away = raw_match["away_team"]["away_team_name"]
    events = events_from_statsbomb(raw_events, home, away, match_id)
    duration = int(max((e.minute for e in events), default=90)) + 1
    return {
        "match_id": match_id,
        "match_date": raw_match.get("match_date"),
        "home_team": home,
        "away_team": away,
        "home_score": raw_match.get("home_score"),
        "away_score": raw_match.get("away_score"),
        "events": events,
        "duration": duration,
    }


# On-ball action types that move or touch the ball — the Digital Match Twin's
# raw material. Everything else (pressure, positioning noise) is skipped.
_STREAM_SEGMENTS = {"Pass", "Carry", "Shot"}          # have an end_location
_STREAM_POINTS = {"Ball Receipt*", "Ball Recovery", "Dribble", "Clearance",
                  "Interception", "Block", "Duel", "Goal Keeper",
                  "Foul Committed", "Miscontrol"}


def ball_stream(raw_events, home_team):
    """The match reconstructed as a dense, timed on-ball stream.

    Every pass, carry and shot in the raw feed carries a real start location,
    end location, sub-second timestamp and duration; point actions (receipts,
    recoveries, duels, ...) carry a location. This function normalizes them to
    one chronological stream — the truth the 2D twin animates. Nothing is
    interpolated here: every coordinate and time is StatsBomb's record of what
    actually happened on the pitch.

    Output items (engine 0-100 frame, acting team's attacking direction):
        {"t": seconds, "type", "team": HOME/AWAY, "player", "player_id",
         "x", "y"} + for segments: {"x2", "y2", "dur": seconds}
    Sorted by t; deterministic.
    """
    out = []
    for e in raw_events:
        etype = e.get("type", {}).get("name")
        loc = e.get("location")
        if not loc or (etype not in _STREAM_SEGMENTS
                       and etype not in _STREAM_POINTS):
            continue
        t = float(e.get("minute", 0)) * 60.0 + float(e.get("second", 0))
        x, y = _rescale(loc)
        player = e.get("player") or {}
        item = {
            "t": round(t, 2),
            "type": etype,
            "team": "HOME" if e.get("team", {}).get("name") == home_team else "AWAY",
            "player": player.get("name"),
            "player_id": str(player["id"]) if player.get("id") is not None else None,
            "x": round(x, 2) if x is not None else None,
            "y": round(y, 2) if y is not None else None,
        }
        if etype in _STREAM_SEGMENTS:
            detail = e.get(etype.lower(), {})
            end = detail.get("end_location")
            if end:
                x2, y2 = _rescale(end)
                item["x2"] = round(x2, 2) if x2 is not None else None
                item["y2"] = round(y2, 2) if y2 is not None else None
            item["dur"] = round(float(e.get("duration") or 0.0), 3)
            if etype == "Shot":
                outcome = detail.get("outcome", {}).get("name")
                item["outcome"] = outcome
        out.append(item)
    out.sort(key=lambda i: (i["t"], i["type"]))
    return out


# --------------------------------------------------------------------------- #
# Live download helpers (used by the ingestion script, never by CI tests)
# --------------------------------------------------------------------------- #
def _http_bytes(url, step=1_000_000, retries=4, timeout=90):
    """GET the full body, tolerating proxies that truncate large responses.

    Some egress proxies cap a single HTTP response (~1.4 MB here), which makes a
    plain ``urlopen().read()`` raise ``IncompleteRead`` on StatsBomb's multi-MB
    event files. We fetch the body in sub-cap HTTP ``Range`` windows and
    concatenate, which the origin (GitHub raw) serves as 206 Partial Content.
    """
    last = None
    for attempt in range(retries):
        try:
            buf = b""
            start = 0
            while True:
                req = urllib.request.Request(
                    url, headers={"Range": f"bytes={start}-{start + step - 1}"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        chunk = resp.read()
                        status = resp.status
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 416 and buf:  # requested past EOF -> done
                        break
                    raise
                buf += chunk
                # 200 == server ignored Range; a short window == final chunk.
                if status == 200 or len(chunk) < step:
                    break
                start += len(chunk)
            return buf
        except Exception as exc:  # noqa: BLE001 - transient network / truncation
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last


def _get_json(url, timeout=90):
    """GET + parse JSON, working around proxy response-size truncation."""
    return json.loads(_http_bytes(url, timeout=timeout))


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
    """A pluggable ``Source`` over StatsBomb open data (post-match replay).

    Bound to one competition/season. The match index (which carries home/away and
    the final score) is loaded once and cached on the instance; ``stream`` then
    maps a single match's events to normalized ``Event`` objects. The loaders are
    injectable so the mapping can be exercised offline, without the network.
    """

    name = "statsbomb"
    base_trust = 0.95  # curated, high-quality event data

    def __init__(self, competition_id, season_id, cache_dir=None,
                 *, matches_loader=None, events_loader=None):
        self.competition_id = competition_id
        self.season_id = season_id
        self.cache_dir = cache_dir
        self._matches_loader = matches_loader or (
            lambda: fetch_matches(competition_id, season_id)
        )
        self._events_loader = events_loader or (
            lambda match_id: fetch_events(match_id, cache_dir=cache_dir)
        )
        self._index = None

    def _match_index(self):
        if self._index is None:
            self._index = {str(m["match_id"]): m for m in self._matches_loader()}
        return self._index

    def matches(self):
        """All raw match records for the bound competition/season."""
        return list(self._match_index().values())

    def match(self, match_id):
        """A backtest-ready match dict (teams, score, mapped events)."""
        raw_match = self._match_index()[str(match_id)]
        raw_events = self._events_loader(match_id)
        return match_dict_from_statsbomb(raw_match, raw_events)

    def stream(self, match_id):
        yield from self.match(match_id)["events"]

    def raw_events(self, match_id):
        """The unmapped StatsBomb event array (needed for player profiling)."""
        return self._events_loader(match_id)

    def player_stats(self, match_id, table=None):
        """Accumulate per-player counters (Section 12) for one match into ``table``."""
        raw_match = self._match_index()[str(match_id)]
        home = raw_match["home_team"]["home_team_name"]
        away = raw_match["away_team"]["away_team_name"]
        return accumulate_player_stats(self.raw_events(match_id), home, away, table)
