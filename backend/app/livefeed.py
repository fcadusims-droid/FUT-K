"""Live feed from football-data.org into a Live-Mode session (Phase 2).

Polling glue between the free ``FootballDataSource`` (``fie.sources.footballdata``)
and the in-process Live Mode engine (``app.live``). ``sync_live`` is the pure,
testable core: given a live session and the provider's current match JSON, it
feeds only the events not seen yet — so repeated polls are idempotent and the
twin's state advances exactly as the real match does. No event is invented: each
fed observation is a goal/card/substitution the provider actually reported.
"""

from __future__ import annotations

import os
from collections import Counter

from fie.sources.footballdata import (
    FootballDataSource,
    current_minute,
    observations_from_match,
)


def _key(obs_or_event) -> tuple:
    minute = obs_or_event["minute"] if isinstance(obs_or_event, dict) else obs_or_event.minute
    type_ = obs_or_event["type"] if isinstance(obs_or_event, dict) else obs_or_event.type
    team = obs_or_event["team"] if isinstance(obs_or_event, dict) else obs_or_event.team
    return (round(float(minute), 3), type_, team)


def sync_live(session, match: dict) -> int:
    """Feed every provider event not already in ``session``; advance its clock.

    Returns the number of newly fed events. Idempotent by *occurrence count*
    per ``(minute, type, team)``: polling the same match twice feeds nothing,
    a genuinely new second event in the same minute (a quick brace) is fed,
    and a provider that fills in the scorer on a later poll does not re-feed
    the goal (the player is deliberately not part of the identity).
    """
    stored = Counter(_key(e) for e in session.events)
    seen: Counter = Counter()
    fed = 0
    for obs in observations_from_match(match):
        key = _key(obs)
        seen[key] += 1
        if seen[key] <= stored[key]:
            continue  # this occurrence was already fed
        session.observe(obs)
        fed += 1
    # Advance the clock to the provider's live minute even when no event landed.
    session.tick(current_minute(match))
    return fed


def sync_live_db(db, match_id: str, match: dict, params):
    """DB-backed live sync: feed new provider events into the persisted session.

    The store-backed twin of ``sync_live`` — the session state lives in the DB
    (so any worker can serve it), and this diffs against the stored observation
    log via ``live.feed``. Returns ``(fed, snapshot)`` or ``(0, None)`` if the
    session does not exist. Idempotent, like the in-memory path.
    """
    from . import live

    obs_list = list(observations_from_match(match))
    result = live.feed(db, match_id, obs_list, params,
                       tick_minute=current_minute(match))
    return result if result is not None else (0, None)


def fetch_live_match(fd_id: int, api_key: str | None = None) -> dict:
    """Fetch one football-data.org match's detail (needs a free key for events).

    Reads the ``FOOTBALL_DATA_API_KEY`` env var when no key is passed. Raises on
    network/HTTP errors — the caller decides how to surface them.
    """
    key = api_key if api_key is not None else os.environ.get("FOOTBALL_DATA_API_KEY")
    return FootballDataSource(key).match(fd_id)
