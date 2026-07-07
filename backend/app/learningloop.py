"""Data pipeline + continuous learning (product levels 18-19).

Level 18 — the automated pipeline:
    ``refresh_pair`` ingests only matches not yet in the DB, runs data-quality
    checks on what arrived, and records every run in ``ingestion_runs`` —
    incremental, idempotent, audited.

Level 19 — the learning cycle (new game → error → update → recalibrate →
new version):
    ``recalibrate`` refits base_rate/tau on all but the most recent quarter of
    a competition's matches, scores both the newly fitted and the currently
    active parameters on that held-out recent block, and **promotes the new
    version only if it does not degrade** held-out log loss. Every attempt —
    promoted or not — is recorded in ``model_versions``; the panel serves the
    latest promoted version.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fie.learning import DEFAULT_TAU_GRID, evaluate, fit_parameters
from fie.prediction import Params
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingest import ingest_match, rebuild_season_profiles
from .models import IngestionRun, Match, MatchEvent, ModelVersion
from fie.sources.statsbomb import StatsBombSource

__all__ = ["refresh_pair", "recalibrate", "get_active_params", "quality_issues"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Level 18 — incremental refresh with quality audit
# --------------------------------------------------------------------------- #
def quality_issues(session: Session, match_id: str) -> list:
    """Data-quality checks for one ingested match. Empty list = clean."""
    m = session.get(Match, match_id)
    events = session.execute(
        select(MatchEvent).where(MatchEvent.match_id == match_id)
    ).scalars().all()
    issues = []
    if not events:
        issues.append(f"{match_id}: no events")
        return issues
    goals_h = sum(1 for e in events if e.type == "goal" and e.team == "HOME")
    goals_a = sum(1 for e in events if e.type == "goal" and e.team == "AWAY")
    if (m.home_goals_final, m.away_goals_final) != (goals_h, goals_a):
        issues.append(
            f"{match_id}: goal events {goals_h}-{goals_a} != final "
            f"{m.home_goals_final}-{m.away_goals_final}"
        )
    max_minute = max(e.minute for e in events)
    if not 30 <= max_minute <= 150:
        issues.append(f"{match_id}: implausible duration {max_minute:.0f} min")
    return issues


def refresh_pair(session: Session, competition_id: int, season_id: int,
                 cache_dir: str | None = None, source=None) -> IngestionRun:
    """Ingest only *new* matches for the pair; audit the run (level 18)."""
    source = source or StatsBombSource(competition_id, season_id, cache_dir=cache_dir)
    existing = {
        row[0] for row in session.execute(
            select(Match.id).where(Match.competition == str(competition_id),
                                   Match.season == str(season_id))
        )
    }
    added, failed = [], []
    skipped = 0
    for raw in source.matches():
        mid = str(raw["match_id"])
        if mid in existing:
            skipped += 1
            continue
        try:
            added.append(ingest_match(session, source, raw["match_id"]))
        except Exception as exc:  # noqa: BLE001 - keep the pipeline going
            failed.append(f"{mid}: {exc}")
    session.commit()

    if added:
        # Keep player profiles in step with the data: rebuild this pair's
        # season accumulation over every match now in the DB (cache-served —
        # nothing is re-downloaded) and re-derive the global profiles.
        rebuild_season_profiles(session, source, competition_id, season_id)

    notes = list(failed)
    for mid in added:
        notes.extend(quality_issues(session, mid))
    run = IngestionRun(
        started_at=_now(), pairs=f"{competition_id}/{season_id}",
        matches_added=len(added), matches_skipped=skipped,
        matches_failed=len(failed), quality_ok=not notes,
        quality_notes="; ".join(notes) or None,
    )
    session.add(run)
    session.commit()
    return run


# --------------------------------------------------------------------------- #
# Level 19 — recalibration with an honest promotion gate
# --------------------------------------------------------------------------- #
def get_active_params(session: Session) -> Params:
    """The latest *promoted* model version, or the engineered defaults."""
    row = session.execute(
        select(ModelVersion).where(ModelVersion.promoted.is_(True))
        .order_by(ModelVersion.id.desc()).limit(1)
    ).scalars().first()
    if row is None:
        return Params()
    return Params(base_rate=row.base_rate, tau=row.tau)


def recalibrate(session: Session, matches: list, competition: str | None = None,
                holdout_share: float = 0.25, window: float = 10.0) -> ModelVersion:
    """One turn of the learning cycle over backtest-ready ``matches`` dicts.

    Train on the older (1 - holdout_share) of matches, evaluate the newly
    fitted params AND the currently active params on the most recent block,
    and promote only if the new version's held-out log loss is not worse.
    """
    if len(matches) < 8:
        raise ValueError("need at least 8 matches to recalibrate honestly")
    ordered = sorted(matches, key=lambda m: (m.get("match_date") or "", m["match_id"]))
    cut = max(1, int(len(ordered) * (1 - holdout_share)))
    train, holdout = ordered[:cut], ordered[cut:]

    active = get_active_params(session)
    fitted = fit_parameters(train, Params(), tau_grid=DEFAULT_TAU_GRID, window=window)
    ll_active = evaluate(holdout, active, window=window)["log_loss"]
    ll_fitted = evaluate(holdout, fitted, window=window)["log_loss"]
    promoted = ll_fitted <= ll_active

    version = ModelVersion(
        created_at=_now(), competition=competition,
        base_rate=fitted.base_rate, tau=fitted.tau,
        holdout_log_loss=round(ll_fitted, 4), baseline_log_loss=round(ll_active, 4),
        promoted=promoted,
        note=("promoted: improves or matches held-out log loss" if promoted
              else "rejected: would degrade held-out log loss"),
    )
    session.add(version)
    session.commit()
    return version
