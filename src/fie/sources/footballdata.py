"""football-data.org connector (Layer 1) — a free, live-capable source.

Maps football-data.org's v4 REST API (https://www.football-data.org/) onto the
normalized ``Event`` model, so the same validated engine that replays StatsBomb
history can also be fed a **live** match. Standard-library only (``urllib`` +
``json``), matching the StatsBomb connector, and with an injectable loader so the
mapping is unit-testable offline.

Access tiers (measured against the live API, 2026-07):

* **Keyless** (rate-limited ~10 req/min): ``/v4/competitions`` and ``/v4/matches``
  (today's live scoreboard — score, status, minute, teams) work with **no key**.
* **Free API key** (``X-Auth-Token`` header; register at football-data.org):
  unlocks match **detail** — ``goals``, ``bookings`` and ``substitutions`` with
  real minutes — across 12 free-tier competitions: Brasileirão (BSA), Premier
  League (PL), La Liga (PD), Bundesliga (BL1), Serie A (SA), Ligue 1 (FL1),
  Eredivisie (DED), Primeira Liga (PPL), Championship (ELC), Champions League
  (CL), European Championship (EC) and the World Cup (WC).

Honesty, as everywhere in FUT-K: football-data.org is match/aggregate level, not
event-grade — it reports goals, cards and substitutions with minutes, but no
shots, passes or coordinates. This connector maps exactly what the provider
reports and **invents nothing**: a goal event carries the provider's recorded
minute and team, never a guessed one. Feeding a live twin therefore drives the
score, the goal/card timeline and everything derived from them; the shot-level
texture of a StatsBomb replay is simply not in this free feed.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..events import Event
from .base import Source

BASE_URL = "https://api.football-data.org/v4"

# football-data.org card values -> normalized event types.
_CARD_TYPE = {"YELLOW": "yellow_card", "RED": "red_card", "YELLOW_RED": "red_card"}

# The 12 competitions available on the free (TIER_ONE) plan, by their codes.
FREE_COMPETITIONS = (
    "BSA", "PL", "PD", "BL1", "SA", "FL1", "DED", "PPL", "ELC", "CL", "EC", "WC",
)


# --------------------------------------------------------------------------- #
# Pure mapping (no I/O) — the tested core.
# --------------------------------------------------------------------------- #
def team_side(match: dict, team_obj: dict | None) -> str | None:
    """Resolve a match-relative side (``HOME``/``AWAY``) for a team object.

    Matches by team id first (stable), then by name; returns ``None`` when the
    team belongs to neither side (so the event is dropped rather than guessed).
    """
    team_obj = team_obj or {}
    home, away = match.get("homeTeam") or {}, match.get("awayTeam") or {}
    tid = team_obj.get("id")
    if tid is not None:
        if tid == home.get("id"):
            return "HOME"
        if tid == away.get("id"):
            return "AWAY"
    name = team_obj.get("name")
    if name:
        if name == home.get("name"):
            return "HOME"
        if name == away.get("name"):
            return "AWAY"
    return None


def _pid(obj: dict | None) -> str | None:
    pid = (obj or {}).get("id")
    return str(pid) if pid is not None else None


def events_from_match(match: dict) -> list[Event]:
    """Normalize one football-data.org v4 match into sorted ``Event`` objects.

    Reads the provider's ``goals``, ``bookings`` and ``substitutions`` arrays
    (present on the match-detail endpoint, which needs a free key). Each event
    carries the provider's own minute and team; entries without a resolvable
    side or minute are skipped, never invented.
    """
    mid = str(match.get("id"))
    out: list[Event] = []

    for g in match.get("goals") or []:
        side = team_side(match, g.get("team"))
        minute = g.get("minute")
        if side is None or minute is None:
            continue
        out.append(Event(match_id=mid, minute=float(minute), team=side,
                         type="goal", player_id=_pid(g.get("scorer"))))

    for b in match.get("bookings") or []:
        etype = _CARD_TYPE.get(b.get("card"))
        side = team_side(match, b.get("team"))
        minute = b.get("minute")
        if etype is None or side is None or minute is None:
            continue
        out.append(Event(match_id=mid, minute=float(minute), team=side,
                         type=etype, player_id=_pid(b.get("player"))))

    for s in match.get("substitutions") or []:
        side = team_side(match, s.get("team"))
        minute = s.get("minute")
        if side is None or minute is None:
            continue
        out.append(Event(match_id=mid, minute=float(minute), team=side,
                         type="substitution", player_id=_pid(s.get("playerIn"))))

    out.sort(key=lambda e: e.minute)
    return out


def observations_from_match(match: dict) -> list[dict]:
    """The match's events as Live-Mode observation dicts (``live.observe``)."""
    return [
        {"minute": e.minute, "team": e.team, "type": e.type, "player_id": e.player_id}
        for e in events_from_match(match)
    ]


def current_minute(match: dict) -> float:
    """Best-effort live clock: the provider ``minute`` when in play, else the
    last event minute, else 0 — never a fabricated clock."""
    if match.get("minute") is not None:
        return float(match["minute"])
    events = events_from_match(match)
    return events[-1].minute if events else 0.0


# --------------------------------------------------------------------------- #
# HTTP source (I/O) — injectable loader keeps the mapping testable offline.
# --------------------------------------------------------------------------- #
def _http_get_json(url: str, api_key: str | None = None, timeout: int = 30) -> dict:
    headers = {"X-Auth-Token": api_key} if api_key else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class FootballDataSource(Source):
    """A pluggable ``Source`` over football-data.org's free v4 API.

    ``api_key`` (or the ``FOOTBALL_DATA_API_KEY`` env var, read by the caller)
    unlocks match detail; without it, only ``competitions()`` and
    ``live_matches()`` (the keyless scoreboard) are available. ``http_get`` is
    injectable so the whole connector runs offline against recorded fixtures.
    """

    name = "football-data.org"
    base_trust = 0.80  # reliable match/aggregate feed, but not event-grade

    def __init__(self, api_key: str | None = None, *, http_get=None) -> None:
        self.api_key = api_key
        self._http_get = http_get or (lambda url: _http_get_json(url, api_key))

    def competitions(self) -> list[dict]:
        """All competitions the API exposes (keyless)."""
        return self._http_get(f"{BASE_URL}/competitions").get("competitions", [])

    def live_matches(self) -> list[dict]:
        """Today's matches / live scoreboard (keyless): score, status, minute."""
        return self._http_get(f"{BASE_URL}/matches").get("matches", [])

    def match(self, match_id) -> dict:
        """One match's full detail (needs a free key for goals/bookings)."""
        data = self._http_get(f"{BASE_URL}/matches/{match_id}")
        return data.get("match", data)

    def stream(self, match_id):
        """Yield normalized ``Event`` objects for a football-data.org match."""
        yield from events_from_match(self.match(match_id))
