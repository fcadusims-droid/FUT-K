# FUT-K architecture — the stable core

FUT-K's biggest long-term risk is not algorithms or data; it is **complexity**.
This document pins the antidote: four layers with one dependency rule, and a
test that fails the build if anyone breaks it.

```text
┌────────────────────────────────────────────────────────────┐
│ APPLICATION   backend/app · frontend · scripts · sdk        │
│               fie.sources · fie.db  (I/O, persistence, UI)  │
├────────────────────────────────────────────────────────────┤
│ KNOWLEDGE     fie.players · fie.coaches · fie.tactical      │
│               fie.narrative · fie.consensus · fie.memory    │
│               fie.causality · fie.explain · fie.profiling   │
│               (reads the model → produces understanding)    │
├────────────────────────────────────────────────────────────┤
│ INFERENCE     fie.learning · fie.learned · fie.ratings      │
│               fie.fusion · fie.simulation · fie.plugins     │
│               (fitting, learning, fusion, simulation)       │
├────────────────────────────────────────────────────────────┤
│ CORE          fie.events · fie.indices · fie.prediction     │
│               fie.regime · fie.confidence · fie.change      │
│               fie.calibration  (the validated math)         │
└────────────────────────────────────────────────────────────┘
```

**The one rule: dependencies point down, never up.**

- **Core** imports nothing but the standard library and other Core modules.
  It is the validated mathematics (89 spec'd test IDs live here). It changes
  rarely and deliberately.
- **Inference** may import Core. Fitting, the learned model, external-baseline
  ratings, the multi-source fusion layer, the future-simulation engine, and
  the plugin registry.
- **Knowledge** may import Core and Inference. The interpretive layer — it
  turns model state into understanding (players, coaches, tactics, narrative,
  explanations).
- **Application** may import anything below. Everything that touches the
  outside world: data sources, persistence, the API, the UI, the scripts.

Enforcement is executable, not aspirational: `tests/test_architecture.py`
parses every module's imports with `ast` and **fails if any module imports
upward**. When the rule genuinely needs to change, change the layer map in
that test in the same commit — the diff then documents the decision.

## Extending FUT-K: plugins, not core edits

Third-party capability lands through the **plugin system**
(`fie.plugins`): a match-metric plugin registers a name, a description, and a
`compute(events, params) -> dict` function that reads Core features. Plugins
live in the repo-root `plugins/` directory (or any directory pointed to by
`FUTK_PLUGINS_DIR`) and are discovered at backend startup; results are served
at `GET /matches/{id}/plugins`. The shipped `plugins/expected_chaos.py` is the
reference: a new metric, zero core edits.

Rules for plugins:

1. Import only `fie` Core/Inference — the architecture test applies to
   `plugins/` too.
2. Pure functions of `(events, params)`: no I/O, no globals, deterministic.
3. Bounded outputs with a human-readable summary — the app renders them as-is.

## What we deliberately did NOT build (yet)

- ~~**Event bus**~~ — **now built** (`fie.eventbus`), on its documented
  trigger: Live Mode (`backend/app/live.py`) streams observations one at a
  time, and the panel + Vision-Engine listeners react to the same published
  event. It stayed deferred until a real concurrent consumer existed; that is
  Live Mode. The bus is a pure, synchronous, deterministic pub/sub — the same
  purity that makes the panel reproducible.
- **Feature store** — Core functions *are* the feature definitions, computed
  on demand from persisted events; materializing them would duplicate state.
- **Experiment tracking service** — `model_versions` (the learning loop's
  audited history) and the generated `validation/results/*` reports cover the
  current need with zero moving parts.

Each of these has a natural trigger written down; adding them early would be
exactly the complexity this document exists to prevent.
