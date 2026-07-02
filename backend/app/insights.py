"""Historical query bank (product level 6): analyze football, not just games.

Preset cross-match queries computed from the persisted events. Each returns
matches with the stat that qualified them, newest-first. ~600 matches scan in
well under a second; precompute later if the bank grows.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Match, MatchEvent


def _match_row(m: Match, stat: str) -> dict:
    return {
        "id": m.id, "competition": m.competition, "match_date": m.match_date,
        "home_team": m.home_team, "away_team": m.away_team,
        "final": f"{m.home_goals_final}–{m.away_goals_final}", "stat": stat,
    }


def _goal_sequence(events) -> list:
    """[(minute, 'HOME'|'AWAY')] in order."""
    return [(e.minute, e.team) for e in events if e.type == "goal"]


def _lead_swings(goals) -> tuple:
    """(max lead HOME had, max lead AWAY had, final diff) from a goal sequence."""
    h = a = 0
    max_h = max_a = 0
    for _, team in goals:
        if team == "HOME":
            h += 1
        else:
            a += 1
        max_h = max(max_h, h - a)
        max_a = max(max_a, a - h)
    return max_h, max_a, h - a


def run_query(db: Session, query: str, team: str | None = None, limit: int = 25) -> list:
    if query not in PRESETS:
        raise ValueError(f"unknown query '{query}'")
    matches = db.execute(select(Match)).scalars().all()
    if team:
        needle = team.lower()
        matches = [m for m in matches
                   if needle in (m.home_team or "").lower()
                   or needle in (m.away_team or "").lower()]

    out = []
    for m in matches:
        events = db.execute(
            select(MatchEvent).where(MatchEvent.match_id == m.id)
            .order_by(MatchEvent.minute)
        ).scalars().all()
        goals = _goal_sequence(events)
        max_h, max_a, final_diff = _lead_swings(goals)

        if query == "comebacks":
            # Trailed by 2+ at some point and avoided defeat (or won).
            if (max_h >= 2 and final_diff <= 0) or (max_a >= 2 and final_diff >= 0):
                side = m.away_team if max_h >= 2 else m.home_team
                out.append(_match_row(m, f"{side} recovered from 2 down"))
        elif query == "blown_leads":
            # Led by 2+ and failed to win.
            if (max_h >= 2 and final_diff <= 0):
                out.append(_match_row(m, f"{m.home_team} led by {max_h} and didn't win"))
            elif (max_a >= 2 and final_diff >= 0):
                out.append(_match_row(m, f"{m.away_team} led by {max_a} and didn't win"))
        elif query == "goal_fests":
            total = len(goals)
            if total >= 5:
                out.append(_match_row(m, f"{total} goals"))
        elif query == "late_drama":
            late = [g for g in goals if g[0] >= 85]
            decisive = [g for g in late]
            if decisive and abs(final_diff) <= 1 and late:
                out.append(_match_row(m, f"{len(late)} goal(s) after the 85th minute"))
        elif query == "card_storms":
            cards = sum(1 for e in events if e.type in ("yellow_card", "red_card"))
            if cards >= 8:
                out.append(_match_row(m, f"{cards} cards"))
        else:
            raise ValueError(f"unknown query '{query}'")

    out.sort(key=lambda r: r["match_date"] or "", reverse=True)
    return out[:limit]


PRESETS = {
    "comebacks": "Comebacks — recovered from 2+ goals down",
    "blown_leads": "Blown leads — led by 2+ and didn't win",
    "goal_fests": "Goal fests — 5+ goals",
    "late_drama": "Late drama — deciders after the 85th minute",
    "card_storms": "Card storms — 8+ cards",
}
