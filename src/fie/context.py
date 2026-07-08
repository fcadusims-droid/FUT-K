"""Contextual Intelligence — deterministic match context (Inference).

The vision's contextual layer (docs/design/DATASET_FUSION.md category 4) helps
interpret events correctly: venue, rest, fixture congestion, competition strength.
This module builds the slice that is **derivable from data already ingested** —
the calendar and the scoreboard — with no external feed and nothing invented.
Weather, altitude and market value need sources the project does not have; they
stay out until such a source exists, rather than being fabricated.

Pure and deterministic: same dates, same numbers. Standard library only.
"""

from __future__ import annotations

from datetime import date
from typing import Optional


def _parse(d: str) -> Optional[date]:
    try:
        return date.fromisoformat(d[:10])
    except (ValueError, TypeError):
        return None


def rest_days(team_match_dates, current_date: str) -> Optional[int]:
    """Days since the team's previous match before ``current_date``.

    ``team_match_dates`` is that team's fixture dates (any order). Returns the gap
    to the most recent earlier match, or ``None`` when this is the team's first
    known match (no prior to measure from — abstain rather than guess).
    """
    cur = _parse(current_date)
    if cur is None:
        return None
    priors = sorted(d for d in (_parse(x) for x in team_match_dates)
                    if d is not None and d < cur)
    if not priors:
        return None
    return (cur - priors[-1]).days


def fixture_congestion(team_match_dates, current_date: str,
                       window_days: int = 14) -> Optional[int]:
    """How many matches the team played in the ``window_days`` before this one.

    A congestion signal (matches in the trailing window, excluding this one).
    Returns ``None`` only when the date is unparseable.
    """
    cur = _parse(current_date)
    if cur is None:
        return None
    count = 0
    for x in team_match_dates:
        d = _parse(x)
        if d is not None and d < cur and (cur - d).days <= window_days:
            count += 1
    return count


def competition_strength(goals_per_match) -> Optional[dict]:
    """A competition's scoring level: mean goals per match over its fixtures.

    ``goals_per_match`` is the list of total-goals-per-match for a competition.
    Returns the mean and sample size (a *derived aggregate*, so it must cite its
    evidence when stored). ``None`` for an empty competition.
    """
    values = [g for g in goals_per_match if g is not None]
    if not values:
        return None
    return {"goals_per_match": round(sum(values) / len(values), 3),
            "matches": len(values)}


def match_context(team, is_home: bool, team_match_dates, current_date: str,
                  window_days: int = 14) -> dict:
    """The deterministic context facts for one team in one match.

    Venue (a hard fact) plus rest and congestion (derived from the calendar).
    Everything here is factual — no model, no inference — so it is stored as
    observed contextual knowledge, not as an estimate.
    """
    return {
        "team": team,
        "venue": "home" if is_home else "away",
        "rest_days": rest_days(team_match_dates, current_date),
        "fixture_congestion": fixture_congestion(team_match_dates, current_date,
                                                 window_days),
    }
