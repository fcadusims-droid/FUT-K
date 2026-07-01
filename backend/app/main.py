"""FastAPI entrypoint. Phase A1 exposes only a health check and a match list —
enough to prove the schema/session wiring works end to end; the real replay and
prediction endpoints land in Phase B.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Match

app = FastAPI(title="Football Intelligence Engine API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/matches")
def list_matches(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Match)).scalars().all()
    return [
        {
            "id": m.id,
            "competition": m.competition,
            "season": m.season,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "home_goals_final": m.home_goals_final,
            "away_goals_final": m.away_goals_final,
        }
        for m in rows
    ]
