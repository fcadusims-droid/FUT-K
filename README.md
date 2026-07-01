# Football Intelligence Engine — mechanics validation

A private AI that watches a live football match the way a coach, a performance
analyst, and a statistician would — at the same time. It does not just compute
statistics; it **interprets, explains, predicts, and learns**. The guiding
question is never *"what will the final score be?"* — it is *"what is really
happening, why, and what tends to happen next?"*

The full design lives in [`football_intelligence_engine.md`](./football_intelligence_engine.md).
This repository is the executable **validation suite** described in
[`validation_test_plan.md`](./validation_test_plan.md): one Python module per
section of the design document, and a falsifiable test per numbered test ID,
running entirely on synthetic / Monte-Carlo data with known ground truth.

## What this milestone proves (and what it does not)

It proves the **engineering is internally consistent** — the Poisson formulas,
the regime logic, the confidence engine, the narrative verification, the
consensus engine, the causality triggers, and the calibration machinery all do
what the document says. It does **not** prove the system understands real
football; that needs real data and the backtest of Section 20.2, which is a
separate, later milestone.

## Layout

```text
src/fie/            # one module per section of the design document
  events.py         # Event / State model (Sec 5)
  indices.py        # pressure, control, momentum (Sec 7)
  prediction.py     # Poisson engine, λ, rates() (Sec 8)
  regime.py         # detect_regime() (Sec 9)
  confidence.py     # confidence() (Sec 10)
  change.py         # change_score() (Sec 11)
  players.py        # decision profile, archetype, influence, network, avatar (Sec 12)
  coaches.py        # coach_profile, coaching_philosophy (Sec 13)
  tactical.py       # tactic detection + collective metrics (Sec 14)
  narrative.py      # opinion->hypothesis, verify, credibility, memory (Sec 15)
  consensus.py      # consensus() (Sec 16)
  memory.py         # remember() / replay() (Sec 17)
  causality.py      # likely_causes() (Sec 18)
  explain.py        # explain() (Sec 19)
  calibration.py    # brier, reliability_curve, backtest (Sec 20)
  learning.py       # fit_parameters, walk-forward split (Sec 21)
tests/              # one test file per module; test IDs map to the plan (T-SS-NN)
  generators/       # synthetic data generators (Part D)
scripts/            # run_monte_carlo.py, report.py -> RESULTS.md
backend/            # FastAPI service: production schema (Postgres/SQLite),
                    #   ingestion pipeline, replay/prediction API (own pyproject)
frontend/           # React + Vite app: match catalog + minute-by-minute replay
                    #   of the Section 22 intelligent panel
```

`src/fie` is **standard-library only**. All third-party dependencies (pytest,
hypothesis, numpy) are test-only and live in the `[dev]` extra. The backend and
frontend are separate packages that consume the engine — see
`backend/README.md` and `frontend/README.md`.

## The app (end to end)

```text
StatsBomb open data ──ingest──> Postgres ──FastAPI──> React replay UI
      (.sb_cache)              (Section 6 schema)    (Section 22 panel)
```

Ingested so far: **462 real matches** (World Cup 2018 complete, all 18
Champions League finals 1970–2019, La Liga 2015/16 complete), 34k+ events,
1.3k player profiles. Pick any match and scrub it minute by minute: the panel
recomputes score, regime, momentum, Poisson predictions with confidence, and
the explained "why" — leakage-safe at every minute.

## Running

```bash
pip install -e ".[dev]"

pytest -q                 # everything, including slow Monte-Carlo / convergence tests
pytest -q -m "not slow"   # fast feedback loop (formula / scenario / invariant)
pytest -q -m "slow"       # Monte-Carlo / convergence only

python scripts/run_monte_carlo.py   # console check of the reference numbers
python scripts/report.py            # regenerate RESULTS.md
```

Every test docstring quotes its **test ID** (e.g. `T-08-03`) so a failure greps
straight back to `validation_test_plan.md`. Monte-Carlo and convergence tests are
marked `@pytest.mark.slow`; the most sensitive ones (the bias mutation, the
no-signal floor, on/off recovery) are additionally parametrized over several
seeds, per the plan's "a test that only passes for one lucky seed is not a
passing test".

## Reference numbers (see `RESULTS.md`)

| Quantity | Reference | Reproduced by |
|---|---|---|
| Goals per match at `BASE_RATE=0.015` | ~2.7 | T-08-06 |
| Brier of a calibrated predictor | ~0.190 | T-20-01 |
| Calibrated reliability deviation | ~0.001 | T-20-03 |
| Source credibility convergence | 0.70 -> ~0.70 | T-15-04 |
| Narrative-memory convergence | 0.18 -> ~0.18 | T-15-09 |
| No information leakage in `backtest()` | hard gate | T-20-04 |

## Real data (Phase 1)

The engine now plugs into **StatsBomb open data** (free, event-level) via a real
`Source`. `scripts/ingest_statsbomb.py` downloads a competition/season, writes it
to SQLite, and runs the same leakage-safe backtest on real events:

```bash
python scripts/ingest_statsbomb.py --competition 43 --season 3 --limit 25
```

First real calibration (2018 World Cup, 25 matches, "goal in next 10 min", 412
scored predictions — see `RESULTS_REAL.md`):

| Metric | Value |
|---|---|
| Real goals/match | 2.40 (engine target ~2.7) |
| Base event frequency | 0.199 (noise floor Brier ≈ 0.159) |
| **Brier** | **0.163** |
| **Log loss** | **0.510** |

The heuristic lands close to the calibration noise floor, and the reliability
curve shows a small, honest over-prediction (predicts ~27% where ~18.5% occur) —
exactly the gap that per-competition parameter fitting (Section 21) exists to
close. `src/fie` stays standard-library only; the connector and DB use
`urllib` / `sqlite3`.

## Fitting (Phase 3-4)

`scripts/fit_statsbomb.py` runs a **walk-forward** fit of `base_rate` and `tau`
per competition: on each expanding past window it tunes the parameters to
minimize log loss, then scores the next block of *future* matches — so any gain
is out-of-sample, not overfitting.

```bash
python scripts/fit_statsbomb.py --competition 43 --season 3 --limit 64 --folds 4
```

On the 2018 World Cup (64 matches, 4 folds, held-out only — see `RESULTS_FIT.md`):

| | Mean predicted | Brier | Log loss |
|---|---|---|---|
| Untuned (`base_rate=0.015`) | 0.275 | 0.1797 | 0.5452 |
| **Fitted (walk-forward)** | **0.211** | 0.1796 | 0.5449 |

Observed event frequency 0.236, so the over-prediction gap `|mean_pred − observed|`
shrinks **0.040 → 0.025** out of sample. Every fold pulls `base_rate` down to
0.010–0.012 (from 0.015), confirming the untuned rate was too high for this
competition. Brier/log loss barely move because at this event rate they are
dominated by the irreducible noise floor; the win is in **calibration** (the mean
prediction moving onto the observed frequency), which is what over-prediction was
about. Not every fold improves (small 12-match test blocks are noisy) — an honest
walk-forward signal, aggregate positive.

### Finals vs regular games — does the model distinguish competitions? (`RESULTS_COMPARE.md`)

`scripts/compare_competitions.py` fits `base_rate`/`tau` per competition (fine
grid) and cross-applies each fit to the others — now including full-league regular
games (a representative sample of La Liga 2015/16), not only finals:

| Competition | Matches | Goals/90 | Fitted base_rate | Fitted tau |
|---|---|---|---|---|
| Champions League finals | 18 | 2.70 | 0.013 | 4 |
| World Cup 2018 | 64 | 2.46 | 0.012 | 4 |
| La Liga 2015/16 (sample) | 50 | 2.28 | 0.012 | 16 |

**Finals score more per 90 minutes** than regular league games, and the model
picks it up: it fits a higher `base_rate` for the finals and — interestingly — a
much longer pressure memory (`tau` 16 vs 4) for the steadier flow of regular
league games. In the cross table **each competition's own parameters beat the
others' on its own data**, so the model *does* distinguish them. (Caveat: the
La Liga sample is 50 of 380 matches and came out below the full-league average of
~2.74 goals/match, so its absolute rate is on the low side; the direction —
finals highest — holds.)

### Per-regime calibration (`RESULTS_REGIME.md`)

`scripts/fit_regime_statsbomb.py` walk-forward-fits a per-regime λ scale on top of
`base_rate`/`tau`. Honest finding: it **does not help** — held-out log loss rises
(0.5449 → 0.5498) and on the full data every regime's best scale is ~1.0. The base
multipliers (pressure, score, time, cards) already encode what the regime label
would add, so the extra per-regime freedom just overfits — exactly Section 24's
warning. The regime detector's value is in **interpretation** (panel, confidence),
not as an extra goal-rate multiplier for this target.

## Player profiles (Section 12) — `RESULTS_PROFILES.md`

`scripts/build_profiles.py` accumulates on-ball events across a competition and
builds each player's DNA — rates/shares, a descriptive archetype, and a
normalized avatar — persisted to the SQLite `player_profiles` table.

```bash
python scripts/build_profiles.py --competition 43 --season 3 --limit 64
```

On the 2018 World Cup (603 players; 465 with >= 60 on-ball actions) the top lists
double as a sanity check and come out right: Harry Kane / Ronaldo / Lukaku /
Cheryshev top the scorers (all `finisher`), and Neymar / Ozil / Muller /
Sigurdsson top the key-pass creators (all `creator`). Archetypes are descriptive
labels read from observed shares — hypotheses, not ground truth (Section 12's
honest-data warning). The connector extracts the rich StatsBomb fields (pass
completion, progression, shot/goal assists, dribbles, turnovers) that the live
`Event` model does not carry; `fie.profiling` derives the profiles
source-agnostically and reuses the validated `players.avatar()`.

### Passing network — Layer 5 (`RESULTS_NETWORK.md`)

`scripts/build_networks.py` builds a team's interaction network from completed
passes (reusing the validated `players.passing_network` / `critical_links` and
`tactical.team_robustness`). On Barcelona 2015/16 (38 league matches) it recovers
their real structure: **robustness 0.933**, dependence only 0.093 (no single
hub), most-central player **Busquets** (the pivot), and the strongest link
**Alba → Neymar (575 passes)** — exactly how that side built play.

### On/off influence — Layer 4 (`RESULTS_INFLUENCE.md`)

`scripts/build_influence.py` reconstructs each player's minutes on the pitch and
compares the team's goals/90 with them on vs off. On Barcelona 2015/16 this is a
textbook demonstration of the **confounder** Section 12 warns about: naive on/off
inverts — rotation players (who enter against weaker/tiring sides) top the list,
while Messi/Iniesta/Piqué show a *negative* delta because they are rested exactly
when the team is already winning big. Presented as a weak descriptive signal, not
a ranking of ability — a causal estimate must control for context.

## Learned model — Stage 3 (`RESULTS_LEARNED.md`)

`fie.learned` is a from-scratch (standard-library) logistic regression over
leakage-safe state features (total pressure, dominance, time, score closeness,
recent shots). `scripts/fit_learned_statsbomb.py` walk-forward-compares it against
the heuristic. **Honest finding: it does not beat the fitted heuristic out of
sample** (held-out log loss 0.5550 vs 0.5449). At this event rate and sample size
the hand-built intensity already sits near the achievable signal, and the walk-
forward discipline correctly *rejects* the learned model — a learned model earns
its place only when it beats the heuristic out of sample (Section 21 / Phase 12).
It should be re-checked as more data and richer features (player avatars) are
added.
