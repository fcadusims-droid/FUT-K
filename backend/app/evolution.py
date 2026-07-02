"""Team memory (product level 9): how a team evolved across a season.

Buckets a team's matches by month and summarizes each bucket from the persisted
events (results, goals, shots, corners, cards for/against), then compares the
first and last thirds of the season for an evolution verdict. Design-doc
Section 17's memory idea lifted from one match to the season.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Match, MatchEvent


def _summary(events, side: str) -> dict:
    opp = "AWAY" if side == "HOME" else "HOME"

    def count(team, *types):
        return sum(1 for e in events if e.team == team and e.type in types)

    return {
        "goals_for": count(side, "goal"),
        "goals_against": count(opp, "goal"),
        "shots_for": count(side, "shot", "shot_on_target"),
        "shots_against": count(opp, "shot", "shot_on_target"),
        "cards": count(side, "yellow_card", "red_card"),
    }


def team_evolution(db: Session, team: str, competition: str | None = None) -> dict:
    needle = team.lower()
    matches = [
        m for m in db.execute(select(Match)).scalars().all()
        if needle in (m.home_team or "").lower() or needle in (m.away_team or "").lower()
    ]
    if competition:
        matches = [m for m in matches if m.competition == competition]
    matches.sort(key=lambda m: m.match_date or "")
    if not matches:
        return {"team": team, "months": [], "verdict": "no matches found"}

    months: dict = defaultdict(lambda: {"matches": 0, "wins": 0, "draws": 0,
                                        "losses": 0, "goals_for": 0, "goals_against": 0,
                                        "shots_for": 0, "shots_against": 0, "cards": 0})
    resolved_name = None
    for m in matches:
        side = "HOME" if needle in (m.home_team or "").lower() else "AWAY"
        resolved_name = m.home_team if side == "HOME" else m.away_team
        events = db.execute(
            select(MatchEvent).where(MatchEvent.match_id == m.id)
        ).scalars().all()
        s = _summary(events, side)
        month = (m.match_date or "????-??")[:7]
        b = months[month]
        b["matches"] += 1
        for k in ("goals_for", "goals_against", "shots_for", "shots_against", "cards"):
            b[k] += s[k]
        gf, ga = s["goals_for"], s["goals_against"]
        b["wins" if gf > ga else ("draws" if gf == ga else "losses")] += 1

    ordered = [{"month": k, **v} for k, v in sorted(months.items())]

    # Evolution verdict: first third vs last third of the season, per-match GD.
    third = max(1, len(ordered) // 3)
    def gd_per_match(bucket_list):
        mts = sum(b["matches"] for b in bucket_list)
        gd = sum(b["goals_for"] - b["goals_against"] for b in bucket_list)
        return gd / mts if mts else 0.0
    early, late = gd_per_match(ordered[:third]), gd_per_match(ordered[-third:])
    delta = late - early
    if delta > 0.3:
        verdict = f"improved: goal difference per match went {early:+.2f} → {late:+.2f}"
    elif delta < -0.3:
        verdict = f"declined: goal difference per match went {early:+.2f} → {late:+.2f}"
    else:
        verdict = f"stable: goal difference per match {early:+.2f} → {late:+.2f}"

    return {"team": resolved_name or team, "months": ordered, "verdict": verdict}
