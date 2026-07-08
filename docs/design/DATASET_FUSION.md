# Dataset Fusion — the unified knowledge substrate

> The Dataset Fusion is FUT-K's central data infrastructure: it unifies,
> normalizes and enriches information from many sources into one complete,
> temporal and contextual representation of football. It is a **knowledge
> model**, not a database — integrating observed, derived, semantic and
> probabilistic knowledge, while guaranteeing that data from different matches,
> seasons, competitions, players or sources is **never mixed indebidamente**.

This document states that target, maps it honestly against what FUT-K ships
today, and defines the phased plan. It obeys the project's founding invariants
(deterministic & reproducible, honest, layered architecture enforced by a test —
see [`ARCHITECTURE.md`](../ARCHITECTURE.md)).

## The founding rule: integrity by isolation

A pass only means something inside the match it happened in. A finishing chance
is only interpretable given that game, that minute, that team, that player. So
the substrate's first commitment is not breadth of data — it is **that every
datum permanently keeps its identity, its context and its origin**, through
every stage of ingestion, transformation, enrichment and query.

That commitment is now code: [`src/fie/fusiondata.py`](../../src/fie/fusiondata.py)
(Inference layer, pure, standard-library only, deterministic), with the contract
tested in [`tests/test_fusiondata.py`](../../tests/test_fusiondata.py).

Every datum is a `KnowledgeRecord` that carries four things it can never shed:

| Part | Guarantees (from the vision) |
|---|---|
| **`Context`** | *where it lives* — competition, season, round, match, date, teams, team, player, event, minute, second. Enrichment may **fill** a field or restate it; it may **never overwrite** an existing value or strip one (`Context.enrich`). |
| **`Provenance`** | *where it came from & how* — the six questions: source, collected-when, ingested-by (process), pipeline version, transformation chain, parent records. Additive: a step is recorded, never erased. A datum with **no source is rejected**. |
| **`Temporal`** | *when it is true* — `valid_from`/`valid_to`/`superseded_by`. Nothing is permanent; a correction **appends** a new version and closes the old one — history is never overwritten. |
| **`Layer`** | *what kind* — the domain separation that keeps inference from contaminating fact (below). |

Identity is deterministic and content-addressed: `record_id(...)` gives a
byte-reproducible id for one *version* of a datum; `logical_key(...)` gives the
version-stable identity of *what it is about*, so a supersede-chain has a stable
anchor and one provider's view is never silently merged into another's.

### Layer separation (the eight domains)

`Layer` splits knowledge so a simulated goal is never confused with an observed
one, and a derived index is worthless without a link to its evidence:

- **Factual** — `OBSERVED`, `HISTORICAL`, `YOUTH`, `EXTERNAL`
- **Inferred** — `DERIVED`, `PROBABILISTIC`, `SIMULATED`, `EXPERIMENTAL`

Inferred records **must cite evidence** (parent records or the producing
pipeline version), enforced at construction by `check_derivation_evidence`.

### Defensive validators — prevention by architecture, not by hope

The vision insists integration errors be *prevented by architecture*, so the
checks **raise** (`IntegrityError`) rather than warn:

| Validator | The rule it enforces |
|---|---|
| `check_provenance` | no datum may exist without a source |
| `check_derivation_evidence` | inferred data must link to its evidence |
| `assert_single_match` | events from different matches are never combined |
| `assert_single_season` | distinct competition/seasons stay separated |
| `assert_single_layer` / `assert_no_fact_inference_mix` | observed reality and model output are never merged as one datum |
| `assert_player_single_team` | a player cannot be on two teams in one match |
| `check_referential_integrity` | an event needs a match; a datum can't point at a player/match that doesn't exist |
| `check_chronology` | event minutes must not run backwards in their recorded order |
| `check_aggregate_consistency` | an aggregate must equal the individual events it summarizes |
| `safe_to_fuse` | fusion only combines independent views of the **same** datum, from **≥2** sources, in **one** layer |

`from_fused_fields` bridges the existing match-reconciliation
([`fie.fusion`](../../src/fie/fusion.py)) into this substrate: each fused field
becomes an `OBSERVED` record that keeps its fused value **and** its honesty
(winning sources, per-field confidence, recorded dissent).

`audit_store` runs the whole validator set over a store on demand — the
*auditoria contínua*: a green run proves the store is internally consistent.
The contract's `SCHEMA_VERSION` travels in provenance so a record written under
an incompatible schema can be rejected.

## Dynamic Knowledge Management — knowledge as a temporal state

[`src/fie/dynamics.py`](../../src/fie/dynamics.py) treats **every attribute as a
state in time, never a permanent fact** (§Gestão Dinâmica do Conhecimento). It is
the timeline machinery over the substrate: each `Temporal` now also carries
`permanence` (permanent vs temporary) and per-version `confidence`.

- **Append-only history.** A change never overwrites: `append_version` closes the
  previous permanent version (`valid_to` + `superseded_by`) and appends the new
  one, so the full history survives.
- **Permanent vs temporary.** A transfer or a settled position switch becomes the
  new current state; an in-match role, a suspension or a false-nine spell is
  `TEMPORARY` — valid only inside its window, overriding the baseline while active
  and reverting when it ends.
- **As-of resolution.** `state_as_of` / `value_as_of` answer any question about
  the past — *how did this player play three seasons ago? when did he stop being
  a striker?* — and `history` returns the full evolution. `current_state` is the
  settled baseline. All deterministic.

## Knowledge Base for Simulation — the leakage-free pre-match state

[`src/fie/worldstate.py`](../../src/fie/worldstate.py) assembles the knowledge the
simulator is handed before kick-off (§Base de Conhecimento para Simulação):

- **`assemble_state(records, as_of)`** resolves every entity attribute *as of* the
  cutoff via `dynamics.state_as_of`, so the simulator sees teams and players as
  they were known before the match — a striker who only became a midfielder later
  is still a striker in a 2020 simulation.
- **`assert_no_future_leak`** is the 73:15 leakage discipline applied to knowledge:
  it rejects any record that becomes valid after the cutoff, was collected after
  it, or is unvalidated inference (`SIMULATED`/`EXPERIMENTAL` can never seed a
  simulation). `assemble_state` runs it by construction.
- **Independence of output.** `simulated_record` tags each result as `SIMULATED`,
  citing the prior-knowledge records that seeded it; `gate_incorporation` refuses
  to admit simulated data into the base without an explicit audit — and even then
  keeps it in the `SIMULATED` layer, never mistaken for observed fact.

## Vision → reality map

Status: ✅ shipped · 🟡 partial · ⬜ planned.

| # | Category in the vision | Status | Where it stands |
|---|---|---|---|
| — | Deterministic pipeline | ✅ | founding invariant, tested everywhere |
| — | **Integrity & isolation contract** | ✅ | **`fie.fusiondata`**: context, provenance, temporal, layers, validators, `audit_store` |
| — | **Dynamic knowledge (temporal versions)** | ✅ | **`fie.dynamics`**: append-only history, permanent/temporary, as-of resolution |
| — | **Simulation knowledge base (leakage-free)** | ✅ | **`fie.worldstate`**: pre-match state as-of a cutoff + simulated-output gating |
| — | Cross-source normalization | ✅ | `fie.fusion.normalize_entity` |
| — | Measured source reliability | ✅ | `fie.fusion.priors_from_agreement` |
| — | Cross-validation without silent overwrite | ✅ | fused fields record dissent, never substitute |
| 1 | Structured data | 🟡 | matches, events, stats, lineups, xG shipped; tracking, transfers, contracts, injuries, rankings ⬜ |
| 2 | Base categories (Sub-13…Sub-23) | 🟡 | `player_season_profiles` + the `YOUTH` layer accept youth as another competition; no dedicated pipeline yet |
| 3 | Unstructured data (NLP) | ⬜ | not started (needs an entity/relation/sentiment extraction stage feeding `EXTERNAL`/`DERIVED`) |
| 4 | Contextual data (weather, altitude, rest, market value) | ⬜ | not started |
| 5 | Temporal data (validity, version history) | ✅ | `Temporal` + `fie.dynamics`: per-version validity, permanence, confidence, append-only history, as-of; persistence of the chain ⬜ |
| 6 | Derived data (embeddings, profiles, indices) | 🟡 | exist (`similarity`, `profiling`, `scouting`); to be re-homed as `DERIVED` records citing evidence |
| 7 | Probabilistic data (Potential, Breakout, MOI, confidence) | 🟡 | predictions/outcomes + `model_versions` shipped; new indices ⬜ |
| 8 | Behavioral data (Leadership, Resilience, …) | ⬜ | not started (derive from event sequences into `DERIVED`) |
| 9 | Simulation data (futures, sub/player impact) | 🟡 | `fie.worldstate` gives the leakage-free pre-match state + output gating; persisting `SIMULATED` records ⬜ |

## What the engine-level Dataset Fusion delivers today

- `src/fie/fusiondata.py` — the substrate: `Context`, `Provenance`, `Temporal`,
  `Layer`, `KnowledgeRecord`, deterministic ids, the full validator set,
  `audit_store`, `SCHEMA_VERSION`, and the `from_fused_fields` bridge.
- `src/fie/dynamics.py` — Dynamic Knowledge Management: append-only version
  timelines, permanent/temporary states, as-of resolution and full history.
- `src/fie/worldstate.py` — the leakage-free pre-match knowledge state for the
  simulator, plus the simulated-output independence gate.
- `tests/test_fusiondata.py`, `tests/test_dynamics.py`, `tests/test_worldstate.py`
  — the contract, tested and deterministic; all three modules are registered in
  the architecture map so the dependency rule and stdlib-only discipline cover them.

It is the **load-bearing foundation**: the guarantee every future category
plugs into. It intentionally does *not* fabricate the nine categories shallowly
— in this project a validated foundation outranks an unvalidated breadth.

## Phased roadmap

**Phase A — engine-level contract ✅.** The record model + isolation/integrity
substrate (`fusiondata`), Dynamic Knowledge Management (`dynamics`) and the
leakage-free Simulation Knowledge Base (`worldstate`), all pure, deterministic
and tested.

**Phase B — persistence & provenance store ✅.** The `knowledge_records` table
(`backend/app/models.py`) and `backend/app/knowledgestore.py`: byte-faithful
serialization (a rebuilt record recomputes the same id), append-only with the
supersede-chain, and every read delegated to the validated engine
(`state_as_of`, `history`, `assemble_state`, `audit`). The fusion pipeline now
also writes each fused field into the store via `from_fused_fields`
(`store_fused_as_knowledge`, wired into `ingest_fused.py`), simulated output is
admitted only through `gate_incorporation` (`store_simulation`), and the
`/knowledge/records|history|as-of|audit` endpoints expose it. Tested in
`backend/tests/test_knowledge_api.py`.

**Phase C — lift existing derived/probabilistic/simulated outputs ⬜.** Re-home
player/match embeddings, profiles and scout indices as `DERIVED` records, and
`/simulate` outputs as `SIMULATED` records — each citing its evidence — with no
new math, only the contract applied.

**Phase D — new categories ⬜.** Contextual data (weather/altitude/rest/market),
behavioral indices, then the unstructured/NLP stage — each entering through the
same front door (`make_record`) so isolation and provenance hold by
construction.

**Phase E — youth pipeline ⬜.** A dedicated `YOUTH`-layer ingestion for the
base categories, feeding Scout AI's trajectory learning (gated today by the lack
of free longitudinal youth data — see [`../SCOUT.md`](../SCOUT.md)).

Every phase keeps the founding promise: deterministic, honest, traceable to
origin, and impossible to contaminate across the boundaries that give data its
meaning.
