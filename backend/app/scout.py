"""Scout AI (Application): similarity, evolution timelines and rankings.

Thin orchestration over the validated engine primitives (``fie.scouting``):
this module only loads real rows from the DB, computes cohort percentiles
against the actually-ingested population, and returns transparent payloads.
Every number traces to observed data; unknown facts (e.g. a missing birth
date) stay unknown and the payload says so.
"""

from __future__ import annotations

from datetime import date

# The archetype-eligibility floor (fie.profiling) doubles as the default
# cohort floor for scouting reads — one source of truth, imported not copied.
from fie.profiling import MIN_ACTIONS
from fie.scouting import age_on, percentile, scout_index, similar_players
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Match, PlayerBio, PlayerProfile, PlayerSeasonProfile

SIMILARITY_NOTE = (
    "Similarity of observed behavioral profile (normalized rates) — proximity "
    "of playing style on real event data, not current quality and not a "
    "potential prediction."
)
RANKINGS_NOTE = (
    "Descriptive scouting index: cohort percentiles of observed rates "
    "(attack, creation, progression, security), weighted by evidence volume "
    "and — when a real birth date is known — an age factor. Filtering by age "
    "only considers players whose birth date is verified (Wikidata); unknown "
    "ages are excluded from age-filtered views rather than guessed."
)


def _profile_dict(row) -> dict:
    return {
        "player_id": row.player_id, "name": row.name, "team": row.team,
        "position": row.position, "actions": row.actions or 0,
        "goals": row.goals or 0, "assists": row.assists or 0,
        "pass_accuracy": row.pass_accuracy or 0.0,
        "progressive_pass": row.progressive_pass or 0.0,
        "key_pass_rate": row.key_pass_rate or 0.0,
        "shot_share": row.shot_share or 0.0,
        "turnover_rate": row.turnover_rate or 0.0,
        "archetype": row.archetype,
        "matches": row.matches, "confidence": row.confidence,
        "sources": (row.sources or "").split(",") if row.sources else [],
    }


def _bio_dict(bio: PlayerBio | None) -> dict | None:
    if bio is None:
        return None
    return {
        "birth_date": bio.birth_date, "height_cm": bio.height_cm,
        "position": bio.position, "citizenship": bio.citizenship,
        "qid": bio.qid, "source": bio.source, "fetched_at": bio.fetched_at,
    }


def similar(db: Session, player_id: str, limit: int = 5) -> dict | None:
    """Players whose observed behavioral profile most resembles this one."""
    rows = db.execute(
        select(PlayerProfile).where(PlayerProfile.actions >= MIN_ACTIONS)
    ).scalars().all()
    by_id = {r.player_id: r for r in rows}
    target = by_id.pop(player_id, None)
    if target is None:
        return None
    candidates = {pid: _profile_dict(r) for pid, r in by_id.items()}
    ranked = similar_players(_profile_dict(target), candidates, limit)
    return {
        "player_id": player_id,
        "name": target.name,
        "similar": [
            {"player_id": pid, "similarity": round(sim, 3),
             "name": by_id[pid].name, "team": by_id[pid].team,
             "archetype": by_id[pid].archetype,
             "confidence": by_id[pid].confidence}
            for pid, sim in ranked
        ],
        "note": SIMILARITY_NOTE,
    }


def evolution(db: Session, player_id: str) -> dict | None:
    """The player's season-by-season timeline + bio + global profile."""
    seasons = db.execute(
        select(PlayerSeasonProfile)
        .where(PlayerSeasonProfile.player_id == player_id)
    ).scalars().all()
    global_row = db.get(PlayerProfile, player_id)
    if global_row is None and not seasons:
        return None
    # Real chronology: order season rows by the earliest ingested match date of
    # that competition/season (season *ids* are not chronological).
    starts = {
        (c, s): d
        for c, s, d in db.execute(
            select(Match.competition, Match.season, func.min(Match.match_date))
            .group_by(Match.competition, Match.season)
        ).all()
    }
    seasons.sort(key=lambda r: (starts.get((r.competition, r.season)) or "",
                                r.competition, r.season))
    bio = db.get(PlayerBio, player_id)
    return {
        "player_id": player_id,
        "name": (global_row.name if global_row else seasons[-1].name),
        "bio": _bio_dict(bio),
        "seasons": [
            {**_profile_dict(r), "competition": r.competition, "season": r.season,
             "first_match_date": starts.get((r.competition, r.season))}
            for r in seasons
        ],
        "overall": _profile_dict(global_row) if global_row else None,
        "note": ("Season rows are per-competition observations; the overall "
                 "profile is their exact sum. Bio facts carry their source "
                 "and entity id; absent means unverified, never guessed."),
    }


def _components(p: dict) -> dict:
    actions = p["actions"] or 1
    return {
        "attack": (p["goals"] + p["assists"]) / actions,
        "creation": p["key_pass_rate"],
        "progression": p["progressive_pass"],
        "security": p["pass_accuracy"] - p["turnover_rate"],
    }


def rankings(
    db: Session,
    position: str | None = None,
    max_age: float | None = None,
    min_actions: int = MIN_ACTIONS,
    min_confidence: float = 0.0,
    competition: str | None = None,
    season: str | None = None,
    limit: int = 25,
    on_date: str | None = None,
) -> dict:
    """The Scout radar: rank a real cohort by the transparent scout index.

    The cohort is the ingested population itself (optionally one competition/
    season); percentiles are computed within it. ``on_date`` fixes "age as of"
    for reproducibility (default: today).
    """
    on = on_date or date.today().isoformat()
    if competition or season:
        stmt = select(PlayerSeasonProfile).where(PlayerSeasonProfile.actions >= min_actions)
        if competition:
            stmt = stmt.where(PlayerSeasonProfile.competition == competition)
        if season:
            stmt = stmt.where(PlayerSeasonProfile.season == season)
    else:
        stmt = select(PlayerProfile).where(PlayerProfile.actions >= min_actions)
    rows = db.execute(stmt).scalars().all()

    bios = {
        b.player_id: b for b in db.execute(select(PlayerBio)).scalars().all()
    }

    pool = []
    for r in rows:
        p = _profile_dict(r)
        if min_confidence and (p["confidence"] or 0.0) < min_confidence:
            continue
        if position:
            hay = " ".join(filter(None, [p["position"], getattr(bios.get(p["player_id"]), "position", None)]))
            if position.lower() not in hay.lower():
                continue
        p["_comps"] = _components(p)
        bio = bios.get(p["player_id"])
        p["_age"] = age_on(bio.birth_date, on) if bio and bio.birth_date else None
        p["_bio"] = _bio_dict(bio)
        pool.append(p)

    if max_age is not None:
        pool = [p for p in pool if p["_age"] is not None and p["_age"] <= max_age]

    populations = {
        k: [p["_comps"][k] for p in pool] for k in ("attack", "creation", "progression", "security")
    }
    ranked = []
    for p in pool:
        pct = {k: percentile(p["_comps"][k], populations[k]) for k in populations}
        idx = scout_index(pct, p["confidence"], p["_age"])
        ranked.append({
            "player_id": p["player_id"], "name": p["name"], "team": p["team"],
            "position": p["position"], "archetype": p["archetype"],
            "actions": p["actions"], "confidence": p["confidence"],
            "age": p["_age"], "bio": p["_bio"],
            "scout": idx,
        })
    ranked.sort(key=lambda r: (-r["scout"]["score"], r["player_id"]))
    return {
        "as_of": on,
        "cohort_size": len(pool),
        "filters": {"position": position, "max_age": max_age,
                    "min_actions": min_actions, "min_confidence": min_confidence,
                    "competition": competition, "season": season},
        "players": ranked[:limit],
        "note": RANKINGS_NOTE,
    }
