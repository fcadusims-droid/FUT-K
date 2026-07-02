# FUT-K

**FUT-K** is a football intelligence app: pick a real match and watch an
AI engine read it minute by minute — who controls the game, which regime the
match is in, what is likely to happen next (with calibrated probabilities and
an honest confidence), and *why*.

> *Don't predict scores — understand football.*

![Match replay — the intelligent panel](docs/images/app-replay-panel.png)

Every number on that panel is recomputed live from the match's event stream
**using only information available up to that minute** — the engine is provably
leakage-free, and the claim is enforced by tests from the math core all the way
up to the HTTP API.

## Quick start

Prerequisites: Python 3.11+, Node 20+, and a PostgreSQL database (SQLite works
for a quick look).

```bash
# 1. backend — API + engine
cd backend
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://user:pw@localhost:5432/futk"   # or omit for SQLite

# 2. ingest real matches (free StatsBomb open data; downloads on demand)
python scripts/ingest.py --pairs "43/3" --limit 20      # World Cup 2018
uvicorn app.main:app --port 8000

# 3. frontend — replay UI
cd ../frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api -> :8000)
```

Open the app, pick a match, press **Play**.

![Match catalog](docs/images/app-match-catalog.png)

## What you get

- **Match catalog** — 462 real matches ready to ingest: the complete 2018
  World Cup, every Champions League final 1971–2019, and the full La Liga
  2015/16 season (StatsBomb open data).
- **The intelligent panel** — score, match regime (NORMAL / PRESSURE /
  POST_GOAL / …), momentum, offensive pressure, Poisson-based predictions
  ("goal in the next 10 minutes: 32%") each carrying a **confidence** that is
  itself calibrated, a change score, and the explained *why*.
- **Replay controls** — play/pause, minute stepping, a momentum timeline with
  goal markers, click-to-seek, and a table view of the whole match.
- **Player DNA** — per-player profiles built from real event data (pass
  accuracy, progression, key passes, archetypes like *finisher* / *creator*),
  served by the API.

## Architecture

```text
StatsBomb open data ──ingest──> PostgreSQL ──FastAPI──> React replay UI
     (event-level)               (backend/)  (REST API)   (frontend/)
                                      │
                               engine: src/fie
                    (pure-Python, standard-library only,
                     207 tests, leakage-safe by construction)
```

| Directory | What it is |
|---|---|
| [`backend/`](./backend/) | FastAPI service: production schema, multi-competition ingestion pipeline, replay/prediction API |
| [`frontend/`](./frontend/) | React + Vite app: the match catalog and the minute-by-minute intelligent panel |
| [`src/fie/`](./src/fie/) | the engine — one module per section of the design document (indices, Poisson prediction, regimes, confidence, players, narrative, calibration, learning) |
| [`validation/`](./validation/) | **empirical validation**: datasets, methodology, metrics, baselines, negative results, and how to reproduce everything |
| [`docs/design/`](./docs/design/) | the founding design document and the numbered validation test plan |
| [`tests/`, `scripts/`](./tests/) | the engine's test suite (89 spec'd test IDs) and the real-data experiment scripts |

## Empirical validation — the evidence

The engine is not just designed to be honest; it is **measured**. Headline
results (full methodology, tables, and reproduction commands in
[`validation/README.md`](./validation/README.md)):

| Claim | Evidence |
|---|---|
| Algorithms match their spec | 89 numbered synthetic tests, multi-seed Monte-Carlo, 216 tests green in CI |
| No information leakage | prediction at minute *t* proven byte-identical when future events are appended — enforced at engine **and** HTTP level |
| Calibrated on real football | walk-forward on WC 2018 (fitting closes a wrong prior: gap 0.040 → 0.025) **and** on all 380 La Liga 2015/16 matches (a right prior stays right: gap 0.009) |
| **Externally anchored** | on real Bet365 odds, the ordering is exactly right: naive baseline (LL 1.050) < Elo (1.007) < **engine's Poisson (0.976)** < market (0.916) — sane machinery, no market-beating claims |
| Multi-target | corners and cards now scored on real data (4,878 held-out snapshots each), not just goals |
| Distinguishes competitions | CL finals score 2.70 goals/90 vs La Liga 2.28; each competition's fitted parameters win on its own data |
| Honest negatives kept | per-regime calibration rejected; learned model rejected; naive pressure-scaling of corners/cards rejected — all by held-out data |
| Player layers face-valid | top scorers/creators recovered correctly (Kane, Neymar, Özil…); Barcelona's passing network recovers Busquets as pivot and Alba→Neymar as the strongest link |

The two rejected experiments stay in the record on purpose: in this project a
validated "no" outranks an unvalidated "yes".

## Design documents

The founding document — the full architecture of the *Digital Model of the
Match*, the twelve intelligences, and the honest-risks list — is
[`docs/design/football_intelligence_engine.md`](./docs/design/football_intelligence_engine.md),
with its executable companion
[`docs/design/validation_test_plan.md`](./docs/design/validation_test_plan.md).

## Roadmap (product phase)

Validation stage is closed — see [`validation/README.md`](./validation/README.md).
Next: FUT-K as a product.

- Live sources + the consensus layer (design doc Sections 4 and 16)
- Richer in-play features (the open research question from validation §7)
- Replicate full-league numbers on more Big-5 seasons
- Passing-network view and player pages in the app

## License & credits

**FUT-K** — created by **João Vitor Perazzolo** (*Johnny Kestler*).

- Code: **AGPL-3.0** (see [`LICENSE`](./LICENSE)) — use it, study it, improve
  it; improvements stay open.
- Commercial licensing available separately — see [`LICENSING.md`](./LICENSING.md).
- Contributions are accepted under the [`CLA`](./CLA.md).
- Match data: [StatsBomb Open Data](https://github.com/statsbomb/open-data),
  under StatsBomb's own non-commercial terms (not redistributed here).
