# Football Intelligence Engine — mechanics validation

A private AI that watches a live football match the way a coach, a performance
analyst, and a statistician would — at the same time. It does not just compute
statistics; it **interprets, explains, predicts, and learns**. The guiding
question is never *"what will the final score be?"* — it is *"what is really
happening, why, and what tends to happen next?"*

The full design lives in [`football_intelligence_engine (3).md`](./football_intelligence_engine%20(3).md).
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
```

`src/fie` is **standard-library only**. All third-party dependencies (pytest,
hypothesis, numpy) are test-only and live in the `[dev]` extra.

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
