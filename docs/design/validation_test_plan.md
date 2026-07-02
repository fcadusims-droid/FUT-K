# Validation & Testing Plan — Football Intelligence Engine

> Companion document to `football_intelligence_engine.md`. This is an execution
> plan: a concrete, numbered list of tests and experiments meant to be picked up
> by **Claude Code**, turned into a real GitHub repository, and run as a normal
> software test suite. Nothing here requires real match data — every test in
> Part C runs on synthetic / Monte-Carlo data with a **known ground truth**, so
> pass/fail is objective. Real-data validation (Section 20.2 of the main
> document) is a separate, later milestone and is only sketched here (Part F).

---

## Ground rules (read first)

1. **No real data needed for any test in this plan.** Every test either (a)
   checks a closed-form formula against itself, (b) checks a formula against a
   Monte-Carlo simulation with a known generator, or (c) checks that code does
   not violate an invariant (e.g. probabilities sum to 1, confidence ∈ [0,1]).
2. **Every test must be falsifiable.** No test should be allowed to pass by
   construction. If a test cannot fail given a broken implementation, rewrite it.
3. **Every numeric pass criterion must be a number**, not "looks reasonable".
   Where the main document already reports a reference number (e.g. Brier
   0.190, deviation 0.0012), reproduce it as a regression target with an
   explicit tolerance.
4. **Tests are organized to mirror the document's section numbers**, so a test
   ID like `T-08-03` means "Section 8, test 3". This makes it trivial to trace
   a failing test back to the spec.
5. **Build bottom-up.** Do not write tests for Section 14 (Tactical
   Intelligence) before Section 7 (indices) is solid — later modules depend on
   earlier ones being correct, and a failure in a foundational module will
   cause confusing cascading failures upstream.

---

## Part A — Repository setup

Claude Code should create the following structure as the first commit:

```text
football-intelligence-engine/
├── src/
│   └── fie/
│       ├── __init__.py
│       ├── events.py          # Event dataclass, normalization (Sec 5)
│       ├── indices.py         # Pressure, control, momentum (Sec 7)
│       ├── prediction.py      # Poisson engine, λ, rates() (Sec 8)
│       ├── regime.py          # detect_regime() (Sec 9)
│       ├── confidence.py      # confidence() (Sec 10)
│       ├── change.py          # change_score() (Sec 11)
│       ├── players.py         # decision_profile, archetype, influence,
│       │                      #   passing_network, avatar (Sec 12)
│       ├── coaches.py         # coach_profile, coaching_philosophy (Sec 13)
│       ├── tactical.py        # pattern detection (Sec 14)
│       ├── narrative.py       # opinion_to_hypothesis, verify, classify,
│       │                      #   divergence_index, credibility,
│       │                      #   collective_state, narrative_memory (Sec 15)
│       ├── consensus.py       # consensus() (Sec 16)
│       ├── memory.py          # remember(), replay() (Sec 17)
│       ├── causality.py       # likely_causes() (Sec 18)
│       ├── explain.py         # explain() (Sec 19)
│       ├── calibration.py     # brier(), reliability_curve(), backtest() (Sec 20)
│       └── learning.py        # fit_parameters(), walk-forward split (Sec 21)
├── tests/
│   ├── conftest.py             # shared fixtures (RNG seed, default params)
│   ├── generators/             # synthetic data generators (Part D)
│   │   ├── __init__.py
│   │   ├── poisson_match.py    # known-λ synthetic match generator
│   │   ├── regime_scenarios.py # hand-built regime fixtures
│   │   ├── narrative_world.py  # synthetic sources with known true accuracy
│   │   └── league_simulator.py # many simulated matches for calibration tests
│   ├── test_indices.py
│   ├── test_prediction.py
│   ├── test_regime.py
│   ├── test_confidence.py
│   ├── test_change.py
│   ├── test_players.py
│   ├── test_coaches.py
│   ├── test_tactical.py
│   ├── test_narrative.py
│   ├── test_consensus.py
│   ├── test_memory.py
│   ├── test_causality.py
│   ├── test_explain.py
│   ├── test_calibration.py
│   ├── test_learning.py
│   └── test_integration_e2e.py
├── scripts/
│   ├── run_monte_carlo.py      # standalone experiment runner (Part C.13)
│   └── report.py               # writes RESULTS.md from pytest + experiment output
├── .github/
│   └── workflows/
│       └── tests.yml           # CI: runs on every push/PR
├── pyproject.toml              # pytest, hypothesis, numpy as deps
├── RESULTS.md                  # generated, not hand-written (Part F)
└── README.md
```

**Conventions for Claude Code:**

- Python ≥3.11, standard library + `pytest`, `hypothesis` (property-based
  testing), `numpy` only if genuinely needed for vectorized Monte Carlo speed.
  Keep `src/fie` itself dependency-free (matches the original document's
  "standard library only" constraint) — test-only dependencies go in a
  `[dev]` extra.
- One module under `src/fie/` per section of the main document, one test file
  per module — keeps the 1:1 traceability the ground rules ask for.
- Each test function's docstring must quote the **test ID** (e.g. `T-08-03`)
  so failures are greppable straight back to this document.
- Commit granularity: one commit per test file getting to green, not one giant
  commit. Open the repo with branch `main` protected; do work on
  `phase-0-skeleton`, `phase-1-…` branches matching Part E, and merge via PR
  once that phase's tests are green in CI.

---

## Part B — Test taxonomy

Every test in Part C is tagged with one of these types:

| Tag | Meaning | Typical assertion |
|---|---|---|
| **FORMULA** | A closed-form formula checked against itself or basic algebra | exact equality / analytic identity |
| **MC** | Monte-Carlo: formula checked against a simulation with known ground truth | within a stated tolerance, large N |
| **INVARIANT** | A property that must hold for *any* valid input | bounds, sums to 1, monotonicity |
| **SCENARIO** | A hand-built input with a known correct output | exact label match |
| **CONVERGENCE** | A statistic must converge to a known true value as data accumulates | within tolerance at large N |
| **REGRESSION** | Reproduces a specific numeric result already reported in the spec | matches reference value ± tolerance |
| **MUTATION** | Deliberately breaks an assumption to confirm the test *can* fail | the system must detect the break |
| **LEAKAGE** | Confirms no future information reaches a past computation | output unchanged when future is altered |

---

## Part C — Master test matrix

### C.7 — Index engine (Section 7)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-07-01 | INVARIANT | `momentum_index` is always in [0,1] | Property-test with `hypothesis`: random event lists, random `tau>0` | `0.0 <= momentum <= 1.0` for 1000+ random cases |
| T-07-02 | FORMULA | With zero events, momentum is exactly 0.5 | Call with empty event list | `momentum_index([], t, tau) == 0.5` |
| T-07-03 | INVARIANT | `offensive_pressure` is monotonically non-decreasing as more same-team events are added | Start from an event list, append one more qualifying event, recompute | `pressure_after >= pressure_before` always |
| T-07-04 | FORMULA | Exponential decay halves correctly | One event at `t - tau*ln(2)` should weigh exactly half of an identical event at `t` | weight ratio = 0.500 ± 1e-9 |
| T-07-05 | SCENARIO | A team with only `shot_on_target` events dominating recently scores momentum > 0.9 | Hand-built event list, all HOME, all `shot_on_target`, last 5 minutes | `momentum_index > 0.9` |
| T-07-06 | INVARIANT | `tau → 0` makes momentum react only to the single most recent event | Two events, one very old one very recent, `tau=0.01` | momentum dominated (>0.99) by the most recent team |
| T-07-07 | INVARIANT | `tau → ∞` makes momentum converge to the unweighted count ratio | Same event list, very large `tau` | momentum ≈ raw count ratio, within 0.01 |
| T-07-08 | FORMULA | Events after `current_minute` are ignored | Add a future event, recompute pressure at an earlier minute | pressure unchanged (this also doubles as a mini leakage check, see T-20-04 for the full version) |

### C.8 — Prediction engine (Section 8)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-08-01 | FORMULA | `poisson_at_least(λ, 0) == 1.0` for any λ | Direct call | exact 1.0 |
| T-08-02 | FORMULA | `poisson_at_least` matches `1 - e^-λ` for k=1 | Direct call vs `math.exp` | equal within 1e-12 |
| T-08-03 | MC | Goal-in-window formula matches simulated frequency | Simulate 200,000 matches with known λ_home, λ_away via `poisson_match` generator; compare `prob_event_within` against the empirical fraction with ≥1 goal in the window | within 0.5 percentage point (reproduces the spec's "Test 1", target ≈ 27–28% for a 10-min window at the calibrated base rate) |
| T-08-04 | MC | `prob_next_goal` matches the empirical share of "which team scores first" | Same simulation, condition on matches with ≥1 goal, check which team scored first | within 0.5 pt of `λ_home/(λ_home+λ_away)` |
| T-08-05 | INVARIANT | `prob_next_goal` always sums to 1.0 (or returns {0.5,0.5} when λ=0) | Property-test over random non-negative λ pairs | `home + away == 1.0 ± 1e-9` |
| T-08-06 | REGRESSION | `BASE_RATE = 0.015` reproduces ≈2.7 goals/match | Simulate 80,000 neutral matches (all multipliers = 1) | mean goals/match in [2.6, 2.8] |
| T-08-07 | INVARIANT | `rates()` never returns a negative λ | Property-test with extreme multiplier inputs (e.g. all multiplier functions forced to their min/max bounds) | both λ ≥ 0 always |
| T-08-08 | MUTATION | A deliberately biased λ (×1.4) must be detectable by later calibration tests | Build a "broken" rates() variant for this test only | this test does not assert calibration itself — it just confirms the biased generator produces a measurably different goal rate than the unbiased one, so T-20-02 has something real to detect |

### C.9 — Regime detector (Section 9)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-09-01 | SCENARIO | Goal scored 2 minutes ago → `POST_GOAL` | Hand-built state/events | exact label |
| T-09-02 | SCENARIO | Red card issued, no other trigger active → `POST_RED_CARD` | Hand-built | exact label |
| T-09-03 | SCENARIO | Minute 85, score tied → `END_GAME` | Hand-built | exact label |
| T-09-04 | SCENARIO | Minute 85, score not tied → `DESPERATION` | Hand-built | exact label |
| T-09-05 | SCENARIO | Minute 40, one team's momentum > threshold → `PRESSURE` | Hand-built | exact label |
| T-09-06 | SCENARIO | Minute 40, balanced momentum → `NORMAL` | Hand-built | exact label |
| T-09-07 | INVARIANT | `detect_regime` always returns one of the six known labels | Property-test over random states | output ∈ the fixed regime set |
| T-09-08 | SCENARIO | Priority order is respected: a post-goal state at minute 86 still returns `POST_GOAL`, not `END_GAME`/`DESPERATION` | Hand-built overlapping-trigger state | `POST_GOAL` |

### C.10 — Confidence engine (Section 10)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-10-01 | INVARIANT | Output always in [0,1] | Property-test, random inputs incl. out-of-range raw values | `0 <= confidence <= 1` |
| T-10-02 | INVARIANT | Monotonic in `n_events`: more data never lowers confidence (all else fixed) | Vary `n_events` only, others fixed | confidence non-decreasing |
| T-10-03 | INVARIANT | Monotonic in `source_quality`, `source_agreement`, `similar_cases` (same method) | Same as above, one factor at a time | non-decreasing |
| T-10-04 | INVARIANT | Monotonic *decreasing* in `regime_instability` | Vary only that factor | confidence non-increasing |
| T-10-05 | MUTATION | One factor at zero collapses confidence near zero even if all others are perfect | Set `f_data=0`, rest at max | confidence < 0.05 (confirms geometric mean behavior, not arithmetic) |
| T-10-06 | REGRESSION | Compare geometric vs arithmetic mean on the same inputs to document the difference | Compute both for a "one bad factor" case | geometric result measurably lower (documents *why* geometric mean was chosen, per the spec's own justification) |

### C.11 — Change detector (Section 11)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-11-01 | SCENARIO | Underdog dominating control *and* leading on the scoreboard → high change score | Hand-built | score > 70 |
| T-11-02 | SCENARIO | Favorite controlling and leading, exactly as expected → low change score | Hand-built | score < 15 |
| T-11-03 | SCENARIO | Balanced game, expected draw → near-zero change score | Hand-built | score < 10 |
| T-11-04 | INVARIANT | Output always in [0,100] | Property-test | `0 <= score <= 100` |
| T-11-05 | INVARIANT | `change_score` is symmetric: swapping which side is "expected" and which is "observed leader" flips the sign of the effect consistently | Construct mirrored home/away scenarios | scores equal under the home/away swap |

### C.12 — Individual Intelligence (Section 12)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-12-01 | INVARIANT | `decision_profile` always sums to 1.0 (or all-zero when no data) | Property-test over random event lists | `sum(probs) == 1.0 ± 1e-9` or all zeros |
| T-12-02 | SCENARIO | A player whose synthetic events are 90% shots on receiving in the box → `archetype == "finisher"` | Hand-built profile dict matching the threshold rules | exact label |
| T-12-03 | SCENARIO | Each of the 5 named archetypes is reachable with a hand-built profile (one test per archetype) | 5 hand-built profiles, one per archetype, each crossing only its own thresholds | each returns its intended label |
| T-12-04 | FORMULA | `goal_influence` is exactly `lambda_on - lambda_off` | Direct call | exact equality |
| T-12-05 | MC | On/off influence recovers a known injected effect | Simulate a team whose λ is multiplied by a known factor `k` only while a synthetic "player" is on the pitch; estimate `lambda_on`/`lambda_off` from the simulated on/off minutes | recovered factor within 5% of `k`, for `k` ranging 0.7–1.5 |
| T-12-06 | INVARIANT | `passing_network` only counts successful passes | Construct events with `success=False` mixed in | unsuccessful passes never appear as graph weight |
| T-12-07 | SCENARIO | `critical_links` correctly identifies the top-`k` highest-volume nodes in a hand-built graph | Hand-built graph with a clear top-3 | exact match, order-insensitive |
| T-12-08 | INVARIANT | Avatar vector is normalized (each dimension in a fixed reference range, e.g. [0,1] after the project's chosen normalization) | Property-test over random raw profiles | every avatar dimension within its declared bounds |
| T-12-09 | INVARIANT | `player_aware_lambda` reduces to `collective_rate` when `mult_lineup` and `network_bonus` are both 1 (neutral) | Direct call with neutral factors | equals the Section 8 baseline λ exactly |

### C.13 — Coach Intelligence (Section 13)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-13-01 | SCENARIO | Profile `{winning: "retreat", losing: "press"}` → `coaching_philosophy` is **not** mislabeled (it should fall to BALANCED per the actual rule, since OFFENSIVE/PRAGMATIC require specific combinations) | Direct call | exact label per the documented rule, not an assumed one — this test exists specifically to catch a mismatch between the prose description and the code |
| T-13-02 | SCENARIO | Profile matching `{losing: "press", winning: "hold"}` → `OFFENSIVE` | Direct call | exact label |
| T-13-03 | SCENARIO | Profile matching `{losing: "hold", winning: "retreat"}` → `PRAGMATIC` | Direct call | exact label |
| T-13-04 | SCENARIO | `coach_adjustment` returns 0.85 only when leading **and** philosophy says retreat | Hand-built state/profile combinations, including the cases that should fall through to 1.0 | exact factor per case |
| T-13-05 | INVARIANT | `coach_adjustment` never returns a value outside {0.85, 1.0, 1.20} given the current rule set | Property-test over all state/profile combinations | output ∈ that fixed set (documents that this is intentionally a coarse, 3-valued function — flags it if someone adds a case without updating this test) |

### C.14 — Tactical & Collective Intelligence (Section 14)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-14-01 | SCENARIO | A synthetic event/position stream with all events in the team's defensive third → classified as `low block` | Hand-built spatial data | exact label |
| T-14-02 | SCENARIO | A synthetic stream with rapid transitions from defensive third to opposite attacking third within <10s windows → classified as `counter-attack` | Hand-built | exact label |
| T-14-03 | INVARIANT | A team whose passing network has one dominant hub (per T-12-07) scores low on "robustness" / high on "dependence on key players" | Construct two synthetic networks: one star-shaped, one evenly distributed | star network's robustness score < distributed network's |
| T-14-04 | INVARIANT | "Cohesion"/"fluidity" metrics are bounded (e.g. [0,1] or [0,100] per implementation choice) | Property-test | within declared bounds |

> Note for Claude Code: Section 14 is the most qualitative module in the spec —
> several of its outputs are labels, not formulas. Where the main document does
> not pin down an exact decision rule, **write the rule down explicitly in code
> first** (a short, documented heuristic), then write the test against *that*
> rule. Do not write a vague test and a vague implementation that happen to
> agree; pin the rule down, then test it.

### C.15 — Narrative Intelligence (Section 15)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-15-01 | SCENARIO | Text containing a known negative word → `direction == "worse"` | Direct call, several hand-picked sentences | exact label, for both Portuguese- and English-flavored fixtures if the system is meant to handle both |
| T-15-02 | SCENARIO | `classify("same", z=0.3)` → `"Confirmed"`; `classify("same", z=2.0)` → `"Strongly contradicted"` | Direct calls across the documented z-score thresholds (0.5, 1.5) | exact label at and around each boundary (test just inside and just outside each threshold) |
| T-15-03 | SCENARIO | `classify("better", z=+2.0)` → `"Confirmed"`; `classify("better", z=-2.0)` → `"Strongly contradicted"` | Direct calls | exact label |
| T-15-04 | CONVERGENCE | A synthetic source with a known true hit rate `p` (e.g. 0.70) → `update_credibility`, applied over thousands of simulated verifications, converges to `p` | Use `narrative_world` generator: draw `Bernoulli(p)` outcomes, feed through `update_credibility` repeatedly | final weight within 0.02 of `p`, for `p` ∈ {0.2, 0.5, 0.7, 0.95} |
| T-15-05 | FORMULA | `divergence_index` is symmetric and non-negative | Property-test | `divergence_index(...) >= 0`; swapping perception/reality and negating gives the same absolute value |
| T-15-06 | SCENARIO | `collective_state`: emotion=10, reality=80, threshold=40 → `overreaction == True` | Direct call | `True` |
| T-15-07 | SCENARIO | `collective_state`: emotion=55, reality=80, threshold=40 → `overreaction == False` (divergence below threshold) | Direct call | `False` |
| T-15-08 | INVARIANT | `collective_state`'s `overreaction` flag is a pure function of `abs(emotion-reality) > threshold` — no hidden dependence on absolute emotion/reality values | Property-test: two input pairs with the same divergence but different absolute levels | identical `overreaction` result |
| T-15-09 | CONVERGENCE | A synthetic recurring narrative pattern with a known true confirmation rate converges via `update_narrative_memory` | Same method as T-15-04, applied to `narrative_memory` instead of source credibility | final rate within 0.02 of true rate after 200+ simulated games (reproduces the spec's "18% in 200 games" reference) |
| T-15-10 | MUTATION | If `verify()`'s z-score is fed a non-finite value (e.g. `ref_std=0` handled, but what about `NaN` real value), the function must not silently return a misleading label | Feed pathological inputs | either a defined error or an explicit "Not confirmed" — never a crash with no signal, and never a false "Confirmed" |

### C.16 — Consensus engine (Section 16)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-16-01 | SCENARIO | Three sources agree on the same claim, weights 0.9/0.7/0.5 vs one dissenting source weight 0.3 → consensus picks the majority claim with `agreement ≈ 0.875` | Hand-built `readings` list | claim correct, agreement within 0.01 |
| T-16-02 | INVARIANT | `agreement` always in [0,1] | Property-test over random reading lists | bounded |
| T-16-03 | SCENARIO | Empty `readings` list → `{"claim": None, "agreement": 0.0}` | Direct call | exact match |
| T-16-04 | SCENARIO | A perfect 50/50 split between two claims of equal total weight → agreement is exactly 0.5, and the claim returned is deterministic given a fixed tie-break rule (document and test the tie-break) | Hand-built tie | matches the documented tie-break behavior, not whatever `max()` happens to do on dict ordering |

### C.17 — Match Memory (Section 17)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-17-01 | INVARIANT | `replay` always returns entries sorted by minute, regardless of insertion order | Insert out of order, then replay | strictly non-decreasing minutes in output |
| T-17-02 | SCENARIO | `remember` appends without mutating earlier entries | Sequence of calls, check earlier entries unchanged | byte-for-byte equal to what was inserted |

### C.18 — Causality Model (Section 18)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-18-01 | SCENARIO | All four triggers active → all four causes returned, in the documented order | Hand-built `features` dict | exact list match |
| T-18-02 | SCENARIO | No triggers active (all features "normal") → empty list | Hand-built | `[]` |
| T-18-03 | INVARIANT | Each individual trigger fires independently of the others (no hidden interaction) | Toggle one feature at a time, others "normal" | only the corresponding cause appears |
| T-18-04 | SCENARIO | Boundary values (e.g. `passes_received_rel` exactly at 0.7) are handled consistently with the documented `<` vs `<=` | Direct call at the exact threshold | matches the documented comparator, not an assumption |

### C.19 — Explanatory Intelligence (Section 19)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-19-01 | SCENARIO | `confidence > 0.66` → no hedge text | Direct call | `note == ""` |
| T-19-02 | SCENARIO | `confidence <= 0.66` → hedge text present | Direct call at and below the boundary | `note != ""` |
| T-19-03 | INVARIANT | Output `because` list length equals the sum of non-empty inputs (`change` contributes 0 or 1 line, plus all of `mechanisms`, `causes`, `drivers`) | Property-test over random combinations | exact count match |

### C.20 — Validation and calibration (Section 20)

This is the most important group in the entire plan — it validates the
validator.

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-20-01 | REGRESSION | `brier()` on a perfectly calibrated synthetic predictor (predictions generated from the *true* λ used to simulate outcomes) reproduces the spec's reference Brier score | Simulate thousands of "goal in 10 min" snapshots from a known λ; predict with the true formula; compute Brier | Brier ≈ 0.190, tolerance ±0.01 |
| T-20-02 | MUTATION | A deliberately biased predictor (λ×1.4, using the biased generator from T-08-08) produces a **worse** Brier score than the calibrated one on the *same* simulated outcomes | Same simulated outcomes, two different predictors | biased Brier > calibrated Brier, and the reliability curve visibly departs from the diagonal (predicted ≈45%, observed ≈33%, reproducing the spec's reference numbers within ±3 pt) |
| T-20-03 | FORMULA | `reliability_curve` on a perfectly calibrated predictor lies on the diagonal | Same calibrated-predictor data as T-20-01 | max deviation from `y=x` across all bands ≤ 0.01 (spec reference: 0.0012) |
| T-20-04 | LEAKAGE | **Critical test.** Run `backtest()` on a synthetic match up to minute `t`; record the prediction. Then append additional synthetic events *after* minute `t` to the same match record and re-run `backtest()` up to the same minute `t`. | The prediction at minute `t` must be **byte-for-byte identical** in both runs — this is the test that proves the no-leakage discipline described in Section 20.2 actually holds in code, not just in prose |
| T-20-05 | SCENARIO | A synthetic "perfectly efficient, no signal" world (predictions equal to the true base rate at all times, no real pattern to find) produces calibration metrics indistinguishable from a properly calibrated model — i.e. the test suite does not manufacture false insight from noise | Simulate matches with **no** injected pattern, confirm Brier/log-loss land at the noise floor expected from the base rate alone | Brier within the theoretical noise floor ± small tolerance |
| T-20-06 | INVARIANT | `brier()` raises or handles gracefully on empty input rather than dividing by zero | Call with `[]` | defined behavior (explicit error or NaN-with-warning, not a silent crash) |

### C.21 — Continuous learning (Section 21)

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-21-01 | MC | `fit_parameters` reduces log loss on the **training** set relative to the untuned starting parameters | Simulate matches with a known but "hidden" optimal `BASE_RATE`/`TAU`; start from deliberately wrong defaults; run the optimizer | post-fit training log loss < pre-fit training log loss |
| T-21-02 | MC | The fitted parameters also reduce log loss on a **held-out** set generated from the same process (walk-forward proxy) | Same setup, evaluate on a disjoint simulated set from the same generator | post-fit held-out log loss < pre-fit held-out log loss |
| T-21-03 | MUTATION | **Overfitting canary.** Fit parameters on a *small, noisy* training set (few matches) and confirm held-out performance can get *worse* than the untuned baseline in at least some seeds — proving the test harness is actually capable of detecting overfitting, not just confirming the happy path | Repeat T-21-02 with `n_train` deliberately small (e.g. 20 matches) across multiple random seeds | at least one seed shows held-out degradation, demonstrating the walk-forward check has teeth |
| T-21-04 | INVARIANT | A walk-forward split never lets a training window and its corresponding test window overlap in time | Property-test over split configurations | `max(train_dates) < min(test_dates)` for every fold |

### C.22 / Integration

| ID | Type | Test | Method | Pass criteria |
|---|---|---|---|---|
| T-INT-01 | INVARIANT | Full pipeline (events → indices → regime → λ → predictions → confidence) runs end-to-end on a simulated match without raising, and every output stays within its documented bounds at every minute | Run one full simulated match through every module in sequence | no exceptions; momentum ∈[0,1]; all probabilities ∈[0,1]; confidence ∈[0,1]; regime ∈ known set |
| T-INT-02 | MC | Across 1,000 full simulated matches, the *panel-level* aggregate predictions (e.g. average predicted goals/match) match the known generator's expectation | Run full pipeline on 1,000 matches, aggregate | within 3% of the generator's true expected goals/match |
| T-INT-03 | SCENARIO | A hand-built "story arc" match (clear regime transitions: NORMAL → PRESSURE → POST_GOAL → END_GAME) produces a Match Memory timeline whose headlines occur in the correct minute order and whose regimes match the expected sequence | Hand-built full match script | exact regime sequence; timeline minutes strictly increasing |

---

## Part D — Required synthetic data generators

Claude Code should build these once, under `tests/generators/`, and reuse them
across the whole suite — they are the foundation every MC and CONVERGENCE test
depends on.

1. **`poisson_match(lambda_home, lambda_away, duration=90, seed=None)`**
   Generates one synthetic match as a list of goal-only events drawn from two
   independent Poisson processes with the given rates. This is the minimal
   generator for Section 8 and 20 tests. Must support an optional list of
   `(minute, multiplier_change)` injections so tests can simulate regime
   changes (e.g. λ jumps after a red card at minute 60).

2. **`narrative_world(true_accuracy, n_opinions, seed=None)`**
   Generates a synthetic "source" whose opinions are correct with probability
   `true_accuracy` and wrong otherwise, paired with synthetic "real" outcomes,
   so credibility-convergence tests (T-15-04) have ground truth to converge to.

3. **`narrative_pattern_world(true_rate, n_games, seed=None)`**
   Same idea as above but for narrative_memory (T-15-09): generates a sequence
   of `confirmed: bool` draws at a known true confirmation rate.

4. **`regime_scenarios()`**
   A fixed, hand-built dictionary of named scenarios (one per regime label)
   used by every SCENARIO test in Section 9, 11, 13, 18 — keep these in one
   place so a change to the regime rules only requires updating fixtures once.

5. **`league_simulator(n_matches, base_rate, seed=None)`**
   Wraps `poisson_match` to produce a whole synthetic league/season, with
   per-match λ drawn from a realistic distribution (not all matches identical)
   — needed for T-08-06, T-20-01–03, T-21-01–03 where a single match isn't
   enough signal.

> All generators must accept and respect a `seed` parameter. CI must run with
> a **fixed seed** for reproducibility, but Claude Code should also run a
> separate nightly/manual job with random seeds across many repetitions to
> catch seed-dependent flakiness — a test that only passes for one lucky seed
> is not a passing test.

---

## Part E — Execution order

Follow this order; do not start a later phase until the previous one is fully
green in CI. This mirrors the roadmap in the main document (Section 23,
Phases 0–3) but broken into testable increments.

```text
Step 1  — Repo skeleton + CI workflow (Part A) running on an empty/trivial test
Step 2  — C.7  Index engine                         (foundation: everything reads this)
Step 3  — C.8  Prediction engine                    (depends on C.7)
Step 4  — C.9  Regime detector                      (depends on C.7, C.8)
Step 5  — C.10 Confidence engine                    (depends on C.9)
Step 6  — C.11 Change detector                      (depends on C.7)
Step 7  — C.20 (T-20-04 leakage test specifically)  → run this BEFORE building
                                                       anything on top of backtest(),
                                                       since every later module's
                                                       validity depends on it
Step 8  — C.12 Individual Intelligence
Step 9  — C.13 Coach Intelligence
Step 10 — C.14 Tactical & Collective Intelligence
Step 11 — C.16 Consensus engine
Step 12 — C.15 Narrative Intelligence (depends on C.16 for credibility weighting)
Step 13 — C.17 Match Memory
Step 14 — C.18 Causality Model
Step 15 — C.19 Explanatory Intelligence (depends on nearly everything above)
Step 16 — C.20 (the remaining calibration tests) + C.21 Continuous learning
Step 17 — C.22 Integration / end-to-end tests
Step 18 — Tag this commit `v0-mechanics-validated` and open the README section
           described in Part F
```

---

## Part F — CI workflow

`.github/workflows/tests.yml`:

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: pip install -e ".[dev]"
      - name: Run unit + scenario + invariant + regression tests (fast, fixed seed)
        run: pytest -q --maxfail=1 -m "not slow"
      - name: Run Monte Carlo / convergence tests (slower, still fixed seed)
        run: pytest -q -m "slow"
      - name: Generate RESULTS.md
        run: python scripts/report.py
      - name: Upload RESULTS.md
        uses: actions/upload-artifact@v4
        with:
          name: results
          path: RESULTS.md
```

Mark MC/CONVERGENCE tests with `@pytest.mark.slow` so the fast feedback loop
(scenario/invariant/formula tests) stays under a few seconds, and the slower
Monte-Carlo tests run as a second, still-required, CI step rather than being
skipped.

---

## Part G — Reporting

`scripts/report.py` should regenerate `RESULTS.md` on every run (never hand-
edited) as a single table:

```text
| Test ID  | Module        | Type        | Status | Observed | Target | Tolerance |
|----------|---------------|-------------|--------|----------|--------|-----------|
| T-08-03  | prediction.py | MC          | PASS   | 27.9%    | 28.3%  | ±0.5 pt   |
| T-20-01  | calibration.py| REGRESSION  | PASS   | 0.191    | 0.190  | ±0.01     |
| ...
```

This is the artifact that answers, mechanically and at a glance, the same
question Section 20.4 of the main document answers in prose: **do the
formulas, the regime logic, the confidence engine, the narrative verification,
the consensus engine, the causality triggers, and the calibration machinery
work as designed?**

---

## Part H — Definition of done for "mechanics validated"

The mechanics are considered validated (equivalent to the main document's
Section 20.4 conclusion) when, and only when:

1. Every test in Part C is green in CI, on at least 3 different random seeds
   for every MC/CONVERGENCE test (not just the CI default seed).
2. `RESULTS.md` shows every REGRESSION test within its stated tolerance of the
   reference values already quoted in `football_intelligence_engine.md`
   Section 20.4 (Brier ≈0.190, deviation ≈0.0012, credibility convergence
   0.70→~0.70, narrative memory 18%→~18%, base rate → ~2.7 goals/match).
3. T-20-04 (the leakage test) passes — this is a hard gate, not a soft one.
   If it fails, no other result in this plan can be trusted, because every
   later module reads from `backtest()`.
4. T-21-03 (the overfitting canary) actually demonstrates degradation in at
   least one seed — if it never does, the test itself is not doing its job
   and must be redesigned with a smaller/noisier training regime until it can
   fail.
5. At least one full T-INT-03 hand-built "story arc" scenario produces a
   Match Memory timeline a human reviewer agrees tells a coherent story.

> What this milestone does **not** prove: that the system understands real
> football. It only proves the engineering is internally consistent and that
> the formulas do what the document says they do. Real-data validation
> (replaying actual historical matches per Section 20.2 of the main document)
> is Phase 3 of the project roadmap and a separate, later body of work — not
> part of this plan.

---

*Validation & testing plan — companion to `football_intelligence_engine.md`.
Every test ID here is designed to be created as a GitHub issue or a single
pytest function by Claude Code, executed, and reported back through
`RESULTS.md`. No test in this plan requires real match data.*
