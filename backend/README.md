# FIE backend (Phase A/B)

FastAPI service for the Football Intelligence Engine. Depends on `fie` (the
validated, dependency-free engine in `../src/fie`) for all football logic; this
package owns persistence (production schema, Section 6) and the HTTP layer.

## Setup

```bash
cd backend
pip install -e ".[dev]"
```

## Database

Any SQLAlchemy URL works via `DATABASE_URL`. Defaults to a local SQLite file for
zero-config dev; point it at Postgres for anything resembling production:

```bash
export DATABASE_URL="postgresql+psycopg://fie_app:<password>@localhost:5432/fie_dev"
python scripts/init_db.py   # creates every table, idempotent
```

## Ingest real data (Phase A2)

Populates matches, events, and player profiles from StatsBomb open data,
reusing the shared `.sb_cache` at the repo root. Idempotent — safe to re-run.

```bash
export DATABASE_URL="postgresql+psycopg://fie_app:<password>@localhost:5432/fie_dev"
python scripts/ingest.py --pairs 43/3 --limit 15   # competition/season pairs
```

## Run

```bash
uvicorn app.main:app --reload
```

- `GET /health` — liveness check
- `GET /matches?competition=` — list ingested matches
- `GET /matches/{id}` — match detail (teams, score, goal minutes, duration)
- `GET /matches/{id}/state?minute=M` — the **intelligent panel** (Section 22) at
  minute M: score, regime, momentum, pressure, predictions with confidence,
  change score, and the explained "why". Leakage-safe: events are sliced at M
  before anything is computed (same discipline as T-20-04).
- `GET /matches/{id}/timeline?step=5` — panel states across the whole match
  (the replay scrubber's data)
- `GET /players/profiles?team=&archetype=&min_actions=` — player DNA profiles

Interactive OpenAPI docs at `/docs` when the server is running.

## Test

```bash
pytest -q
```

Tests run against an in-memory SQLite database — no external service required.
`scripts/init_db.py` is what you point at a real Postgres instance to verify the
schema there; it is not part of the test suite (CI doesn't run a Postgres
service yet — see Phase A2/B for when the ingestion pipeline needs one).
