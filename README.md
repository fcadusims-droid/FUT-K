# FUT-K

**FUT-K is a Digital Football Twin** ([vision](./docs/VISION.md)): a living
computational representation of a football match that reconstructs the past,
understands the present, evaluates decisions (What If?), and turns tactical
intelligence into a visual, interactive, explainable experience. Pick a real
match and watch the engine read it minute by minute — who controls the game,
what is likely to happen next (with calibrated probabilities and an honest
confidence), and *why*.

> *"See the game beyond the game."*

![Match replay — plain-language panel and the narrated Match Story](docs/images/app-replay-panel.png)

Every number on that panel is recomputed live from the match's event stream
**using only information available up to that minute** — the engine is provably
leakage-free, and the claim is enforced by tests from the math core all the way
up to the HTTP API.

The **Digital Match Twin** turns that stream into a living 2D pitch: the ball
follows every recorded pass, carry and shot — real locations, real sub-second
timings, ~3,300 on-ball actions per match — while player dots glide between
their own recorded touches, names appear as they act, goals flash where they
actually happened, and a commentator line narrates as the clock runs the full
90'+ (extra time included) at 0.25× to 32×. Facts are cross-checked against
independent providers by the fusion layer (the ✓ chip):

![Digital Match Twin — the living 2D pitch, animated from real recorded actions](docs/images/app-pitch-replay.png)

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
- **Digital Match Twin** — the living 2D pitch: the full match (90'+ and
  extra time) animated from every recorded pass, carry and shot at 0.25×–32×,
  in standard, minimalist **TV** or **analysis** mode (activity zones,
  momentum arrow, pressure glow); pause anywhere and ask **why?** — the
  engine explains the moment. Honest by construction: every coordinate is
  provider truth or an interpolation between one player's own recorded
  positions; nothing on the pitch is invented.
- **Future Simulation Engine** — from any minute, run 10,000 seeded
  Monte-Carlo simulations of the *remaining* match (a horizon derived from the
  match's real recorded duration — never a hardcoded 90) and see the outcome
  distribution and **opportunity windows**: the lanes and time slices where
  the next chance is most likely. Deterministic (the seed is shown) and
  calibrated (the Monte-Carlo provably converges to the analytic Poisson from
  the same validated rates).

  ![Future Simulation — thousands of futures, bounded by the match's real remaining time](docs/images/app-future-sim.png)
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
                     221 tests, leakage-safe by construction)
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
| Algorithms match their spec | 89 numbered synthetic tests, multi-seed Monte-Carlo, 278 tests green in CI |
| No information leakage | the **73:15 test** (§ below): 5,499 erase-the-future comparisons over all 611 matches, 100% byte-identical — enforced at engine **and** HTTP level on every push |
| Calibrated on real football | walk-forward on WC 2018 (fitting closes a wrong prior: gap 0.040 → 0.025) **and** on all 380 La Liga 2015/16 matches (a right prior stays right: gap 0.009) |
| **Externally anchored** | on real Bet365 odds, the ordering is exactly right: naive baseline (LL 1.050) < Elo (1.007) < **engine's Poisson (0.976)** < market (0.916) — sane machinery, no market-beating claims |
| Multi-target | corners and cards now scored on real data (4,878 held-out snapshots each), not just goals |
| Distinguishes competitions | CL finals score 2.70 goals/90 vs La Liga 2.28; each competition's fitted parameters win on its own data |
| Honest negatives kept | per-regime calibration rejected; learned model rejected; naive pressure-scaling of corners/cards rejected — all by held-out data |
| Player layers face-valid | top scorers/creators recovered correctly (Kane, Neymar, Özil…); Barcelona's passing network recovers Busquets as pivot and Alba→Neymar as the strongest link |
| **Cross-provider truth** | 3 independent providers fused deterministically (majority voting, provenance, recorded dissent); goals and half-time scores agree 100% — and the vote caught a real blind spot in our own extraction (own goals) |

The two rejected experiments stay in the record on purpose: in this project a
validated "no" outranks an unvalidated "yes".

## The 73:15 test — proof the predictions are real

One question defines whether an in-play model is honest:

> *Stop a match at exactly 73:15 and erase everything that happened after
> that instant. Does FUT-K still produce **exactly** the same prediction it
> produced originally?*

If yes, the model does not depend on the future. If no, information is
leaking. We ran this adversarially, on real data, at three levels — and the
answer is yes at every one:

**1. The literal scenario — Belgium 3–2 Japan (WC 2018), stopped at 73:15.**
The most famous comeback in the dataset, chosen on purpose: at 73:15 Japan
led 2–1, and the 24 erased events include both of Belgium's comeback goals.

```text
prediction with full history : goal_next_10min: 0.19, next_goal: {home: 0.695, away: 0.305}
prediction with future erased: goal_next_10min: 0.19, next_goal: {home: 0.695, away: 0.305}
byte-identical panels: True
```

The 69.5% next-goal lean toward Belgium comes from Belgium's pressure *up to
that minute* — not from knowing the comeback happened.

**2. At scale, engine level.** Every ingested match (611, across all six
competitions) × 9 cutoffs each, including 73.25 and the 44.9' edge just
before half-time: **5,499 comparisons, 5,499 byte-identical (100%)**.

**3. The deployed path, database included.** For 24 sampled matches we
created clones whose post-cutoff events were **deleted from the database
itself**, then compared the live API's responses (`/state`, `/state/human`,
`/explain`) between original and clone: **360 comparisons, 360
byte-identical**. Not a promise about the code — a measurement of the
running service.

Reproduce it yourself on whatever you have ingested (including your own
datasets):

```bash
cd backend
python scripts/prove_no_leakage.py     # exits non-zero on any leakage
```

And the property is not a one-off audit: it fails the build on every push —
T-20-04 at the engine level (`pytest tests/test_calibration.py -k leak`) and
the HTTP-level twin (`cd backend && pytest tests/test_replay_api.py -k leak`).

One honest boundary: in the 2D **replay** the ball glides toward the *next*
recorded touchpoint — that uses the future, because a replay is a
visualization of a finished match, not a prediction. Every predictive number
on screen (probabilities, momentum, regime, confidence) comes from the
sliced panel proven above.

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

## Bring your own data

FUT-K is not married to its datasets. Anyone can ingest their own event data
(an open CSV/JSON format — 7 fields) and **calibrate the model on it**, with
the same held-out promotion gate that protects the official numbers:

```bash
cd backend
python scripts/ingest_custom.py --file my_events.csv --competition my-league
python scripts/recalibrate.py   --from-db --competition my-league
```

Your matches replay in the app (2D pitch included), and the refit ships only
if it does not degrade held-out log loss — the gate means you cannot hurt
yourself. Full walkthrough: [`docs/CUSTOM_DATA.md`](./docs/CUSTOM_DATA.md),
sample dataset in [`examples/`](./examples/).

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
