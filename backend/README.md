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

## Run

```bash
uvicorn app.main:app --reload
```

- `GET /health` — liveness check
- `GET /matches` — list matches currently in the DB (populated by the Phase A2
  ingestion pipeline; empty on a fresh database)

## Test

```bash
pytest -q
```

Tests run against an in-memory SQLite database — no external service required.
`scripts/init_db.py` is what you point at a real Postgres instance to verify the
schema there; it is not part of the test suite (CI doesn't run a Postgres
service yet — see Phase A2/B for when the ingestion pipeline needs one).
