# FIE backend (Phase A/B)

FastAPI service for the Football Intelligence Engine. Depends on `fie` (the
validated, dependency-free engine in `../src/fie`) for all football logic; this
package owns persistence (production schema, Section 6) and the HTTP layer.

## Setup

The backend depends on the engine package `fie` (in `../src`), which is not on
PyPI — install it first, from the repo root:

```bash
pip install -e .                  # the engine (fie)
pip install -e "./backend[dev]"   # this service
cd backend
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
- `GET /matches/{id}/events` — normalized events with real pitch coordinates
  and player identity (the 2D pitch replay's raw material)
- `GET /matches/{id}/replay2d` — the Digital Match Twin's dense on-ball stream
  (every pass/carry/shot with real start+end locations and sub-second timing)
- `GET /matches/{id}/crosscheck` — multi-provider verification of the
  fixture's facts (resolves it in the fusion layer's `fused_matches`)
- `GET /matches/{id}/whatif?minute=&type=&team=` — What If?: remove one real
  event and re-run the engine (baseline vs counterfactual series)
- `GET /matches/{id}/simulate?minute=&n_sims=&seed=` — Future Simulation
  Engine: seeded Monte-Carlo projection of the remaining match (horizon from
  the match's real duration), outcome distribution + opportunity windows
- `GET /matches/{id}/tactics?minute=` — the Visual Twin's intelligent-field
  geometry: per-team engagement lines, corridor tendencies, territory, joined
  with the live goal probability
- `GET /matches/{id}/decisions?minute=&team=&seed=` — Strategic Assistant:
  candidate in-match approaches re-simulated and ranked by win-probability delta
- `GET /matches/{id}/vision?minute=&evaluate=` — Vision Engine: the continuous
  estimated state of every entity (position + confidence, held between real
  observations), with optional self-evaluation of its prediction error
- `POST /live/{id}/start`, `POST /live/{id}/observe`, `GET /live/{id}/state`,
  `POST /live/{id}/replay_feed?upto=` — Live Mode: stream observations one at a
  time through the event bus; the streamed state provably equals the batch panel
- `POST /live/{id}/footballdata?fd_id=` — feed a live session from the free
  football-data.org API (idempotent polling; see `docs/DATA_SOURCES.md`)
- `GET /players/profiles?team=&archetype=&min_actions=&min_confidence=` —
  player DNA profiles with evidence-based confidence and provenance
- `GET /players/{id}/similar` · `GET /players/{id}/evolution` — Scout AI:
  behavioral similarity and the season-by-season evolution timeline
- `GET /scout/rankings?position=&max_age=&min_confidence=` — the Scout radar
  (transparent index over the ingested cohort; see `docs/SCOUT.md`)
- `GET /model/versions` — the learning loop's audited version history
- `GET /fusion/records` — cross-provider fused match records with per-field
  provenance (populate with `python scripts/ingest_fused.py`)

Interactive OpenAPI docs at `/docs` when the server is running.

## Test

```bash
pytest -q
```

Tests run against an in-memory SQLite database — no external service required.
`scripts/init_db.py` is what you point at a real Postgres instance to verify the
schema there; it is not part of the test suite (CI doesn't run a Postgres
service yet — see Phase A2/B for when the ingestion pipeline needs one).
