# FUT-K

**FUT-K** is a football intelligence app: pick a real match and watch an
AI engine read it minute by minute — who controls the game, which regime the
match is in, what is likely to happen next (with calibrated probabilities and
an honest confidence), and *why*.

> *Don't predict scores — understand football.*

![Match replay — plain-language panel and the narrated Match Story](docs/images/app-replay-panel.png)

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

**Explore** turns the engine into a query system over football history — real
comebacks, blown leads, late drama — across every ingested match:

![Explore — historical queries](docs/images/app-explore.png)

## What you get

- **Match catalog** — 611 real matches ready to ingest: the complete 2018 and
  2022 World Cups, Euro 2024, every Champions League final 1971–2019, the full
  La Liga 2015/16 season, and Leverkusen's unbeaten Bundesliga 2023/24
  (StatsBomb open data).
- **A plain-language panel** — "Belgium has the upper hand right now. A goal
  in the next 10 minutes is plausible (27%)." No jargon by default; the full
  technical panel (regimes, confidence, momentum, prediction meters) lives
  behind an **Analyst mode** toggle.
- **Match Story** — the narrated timeline: kick-off, goals in context, "the
  game changed" beats, momentum swings, full time. Click a beat to jump the
  replay there.
- **Signature visuals** — Momentum Timeline with goal markers, Pressure Index,
  Confidence Curve; play/pause, minute stepping, click-to-seek, table view.
- **Explore** — preset historical queries (comebacks from 2 down, blown leads,
  goal fests, late drama, card storms) with a team filter.
- **Ask the engine** — "what happened after minute 60?", "why did they lose?",
  "did the referee change the game?" — deterministic answers built from the
  engine's own reading (no external language model).
- **Similar matches** — semantic search by game dynamics: momentum flow, goal
  timing, swings. "Matches that felt like this one."
- **Benchmarks tab** — the validated public numbers, each with the one command
  that reproduces it.
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
                     214 tests, leakage-safe by construction)
```

| Directory | What it is |
|---|---|
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | **the stable core**: 4 layers (Core → Inference → Knowledge → Application), one dependency rule, enforced by a test |
| [`plugins/`](./plugins/) | drop-in match-metric plugins (reference: `expected_chaos`) — extend FUT-K with zero core edits |
| [`backend/`](./backend/) | FastAPI service: production schema, multi-competition ingestion pipeline, replay/prediction API |
| [`frontend/`](./frontend/) | React + Vite app: the match catalog and the minute-by-minute intelligent panel |
| [`src/fie/`](./src/fie/) | the engine — one module per section of the design document (indices, Poisson prediction, regimes, confidence, players, narrative, calibration, learning, fusion) |
| [`validation/`](./validation/) | **empirical validation**: datasets, methodology, metrics, baselines, negative results, and how to reproduce everything |
| [`docs/design/`](./docs/design/) | the founding design document and the numbered validation test plan |
| [`tests/`, `scripts/`](./tests/) | the engine's test suite (89 spec'd test IDs) and the real-data experiment scripts |

## Empirical validation — the evidence

The engine is not just designed to be honest; it is **measured**. Headline
results (full methodology, tables, and reproduction commands in
[`validation/README.md`](./validation/README.md)):

| Claim | Evidence |
|---|---|
| Algorithms match their spec | 89 numbered synthetic tests, multi-seed Monte-Carlo, 257 tests green in CI |
| No information leakage | prediction at minute *t* proven byte-identical when future events are appended — enforced at engine **and** HTTP level |
| Calibrated on real football | walk-forward on WC 2018 (fitting closes a wrong prior: gap 0.040 → 0.025) **and** on all 380 La Liga 2015/16 matches (a right prior stays right: gap 0.009) |
| **Externally anchored** | on real Bet365 odds, the ordering is exactly right: naive baseline (LL 1.050) < Elo (1.007) < **engine's Poisson (0.976)** < market (0.916) — sane machinery, no market-beating claims |
| Multi-target | corners and cards now scored on real data (4,878 held-out snapshots each), not just goals |
| Distinguishes competitions | CL finals score 2.70 goals/90 vs La Liga 2.28; each competition's fitted parameters win on its own data |
| Honest negatives kept | per-regime calibration rejected; learned model rejected; naive pressure-scaling of corners/cards rejected — all by held-out data |
| Player layers face-valid | top scorers/creators recovered correctly (Kane, Neymar, Özil…); Barcelona's passing network recovers Busquets as pivot and Alba→Neymar as the strongest link |
| **Cross-provider truth** | 3 independent providers fused deterministically (majority voting, provenance, recorded dissent); goals and half-time scores agree 100% — and the vote caught a real blind spot in our own extraction (own goals) |

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

- Live sources feeding the fusion layer (design doc Section 4 — the Section 16
  consensus idea already ships as `fie.fusion`, proven on three real providers;
  see validation §5.8)
- Richer in-play features (the open research question from validation §7)
- Replicate full-league numbers on more Big-5 seasons
- Player pages in the app

Also in the repo: **SDKs** (Python + JavaScript, [`sdk/`](./sdk/)), the
**user guide** ([`docs/guide/`](./docs/guide/)) explaining Confidence, Regimes,
Consensus and the panel, and the **product definition**
([`docs/product/PRODUCT.md`](./docs/product/PRODUCT.md)).

## Running it as a service

```bash
docker compose up --build     # postgres + backend (:8000) + frontend (:8080)
```

Operations are built in: `GET /metrics` (per-route latency/errors) and
`/metrics/prometheus`; optional API keys + rate limiting via env
(`FUTK_API_KEYS`, `FUTK_RATE_LIMIT`); incremental audited data refresh
(`backend/scripts/refresh.py`, history in `ingestion_runs`); and the
**continuous learning cycle** (`backend/scripts/recalibrate.py`) — refit on
new data, promote **only if held-out metrics don't degrade**, version history
at `GET /model/versions`, the panel always serving the latest promoted
version. See [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) and
[`PRIVACY.md`](./PRIVACY.md).

## License & credits

**FUT-K** — created by **João Vitor Perazzolo** (*Johnny Kestler*).

- Code: **AGPL-3.0** (see [`LICENSE`](./LICENSE)) — use it, study it, improve
  it; improvements stay open.
- Commercial licensing available separately — see [`LICENSING.md`](./LICENSING.md).
- Contributions are accepted under the [`CLA`](./CLA.md).
- Match data: [StatsBomb Open Data](https://github.com/statsbomb/open-data),
  under StatsBomb's own non-commercial terms (not redistributed here).
