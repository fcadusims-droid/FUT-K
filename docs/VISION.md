# FUT-K Vision — the Digital Football Twin

> **"See the game beyond the game."**

FUT-K is not a statistics app. Not a score predictor. Not a dashboard. Not a
video replay.

**FUT-K is a digital twin of the match.** While a game is played — or while a
historical game is replayed — FUT-K maintains a complete computational
representation of the state of the match. That state evolves continuously:
every pass, every carry, every shot, every pressure change, every card, every
substitution modifies the digital model. The goal is not to show what
happened; it is to show **what is happening, what can happen, and why**.

## The definitive definition

> FUT-K is a **Digital Football Twin**: a living computational representation
> of a football match, able to reconstruct the past, understand the present,
> simulate possible futures, and turn tactical intelligence into a visual,
> interactive, explainable experience.

This places FUT-K in its own category — not competing with stats sites or
prediction models, but offering a different way to *explore* a football
match.

## Two synchronized worlds

Imagine a 2030 World Cup broadcast. On screen, two worlds in sync:

```text
┌──────────────────────────────────────────────────┐
│   LIVE BROADCAST — the reality                   │
│--------------------------------------------------│
│   DIGITAL MATCH TWIN (FUT-K)                     │
│   the invisible structure of that reality:       │
│   players · ball · lines · spaces · vectors ·    │
│   zones · probabilities · explanations           │
└──────────────────────────────────────────────────┘
```

The video shows players running. The twin shows **knowledge**: the corridor
that just opened between full-back and centre-back, who is controlling the
game, where the next advantage will appear — drawn on the pitch as it forms,
before the broadcast commentary catches up.

## What already ships today

The twin is not a promise — its foundations are live in this repository, all
deterministic and honest by construction:

| Vision component | Status | Where |
|---|---|---|
| **Football Data Fusion Engine** — many sources, one truth, per-field provenance and measured reliability | ✅ shipped | `fie/fusion.py`, 4 leagues, 1,372 fused fixtures |
| **Digital Match Twin (historical)** — the match reconstructed second by second from real recorded actions; ball and players animated from provider truth over the full 90'+ | ✅ shipped | `/matches/{id}/replay2d` + the 2D pitch |
| **Inference Engine** — momentum, pressure, regimes, calibrated predictions, confidence, every number leakage-proven (the 73:15 test) | ✅ shipped | `fie/` core + the panel |
| **Decision Intelligence (first step)** — What If? counterfactuals: remove a real event, re-run the engine, compare readings | ✅ shipped | `/matches/{id}/whatif` |
| **Visual Intelligence** — replay / TV / analysis / **tactics** layers: activity zones, pressure glow, engagement lines, territory, opportunity corridors, AI ticker, explain-on-pause | ✅ shipped | the replay UI, `/matches/{id}/tactics` |
| **Tactical reasoning** — the intelligent field (engagement lines, territory, opportunity corridor with live probability) + deterministic Q&A | ✅ shipped | `/matches/{id}/tactics`, `/matches/{id}/ask` |
| **Future Simulation Engine** — thousands of seeded forward simulations from the current state, bounded by the match's real remaining time; outcome distribution + opportunity windows (lane + timing) | ✅ shipped | `fie/simulation.py`, `/matches/{id}/simulate` |
| **Live mode** — the same twin fed by live multi-source feeds through the fusion layer | 🔭 next | fusion + event bus trigger documented in `docs/ARCHITECTURE.md` |
| **Strategic assistant** — "which substitution raises win probability most?" | 🔭 later | the future-simulation engine it needs now exists |

## The reconstruction promise (and its honest boundary)

Put the recorded broadcast of a match side by side with FUT-K's 2D twin and
the ball and players move *like the real game* — because every coordinate is
the provider's record of that same match: ~2,000 timed pass/carry/shot
trajectories and ~3,300 on-ball actions per game, cross-checked against
independent providers by the fusion layer (the ✓ chip in the replay header).

The boundary, stated plainly: event data records players **when they act**.
Between touches, a player dot interpolates only between that player's own
recorded positions, and a player with no recent data honestly disappears —
FUT-K does not fabricate off-ball runs. Full 22-player continuity requires
tracking data; the twin's architecture is ready for it, and the honesty rule
(*nothing on this pitch is invented*) is non-negotiable either way.

## Real time, never fake time

A simulation of a historical match can only run as long as the match really
ran. The horizon is **derived from data, not assumed**: the twin stream's last
recorded second — validated across all 611 ingested matches (100% carry
period/`Half End` markers; durations span 89.9–126.1 minutes, 19 with extra
time; the stream's end agrees with the period marker to within ~3 seconds) —
tells the engine exactly when the match ends. Simulate at minute 88 of a match
that really ran to 95.8' and the engine projects **7.8 minutes**, not a
hardcoded 90. Cross-provider agreement on the final score (the fusion layer)
corroborates that the match completed. No fake time enters anywhere.

## Philosophy

Most platforms answer: *what happened?*

FUT-K answers: **what is happening? what can happen? why can it happen? what
changes if we decide differently?**

The rendering seeks clarity, not realism — a light vector pitch that runs in
any browser, on any phone, at low latency. The value is in the information.

## Conceptual architecture

```text
data providers
      ↓
Football Data Fusion Engine     (shipped — deterministic, provenance, dissent)
      ↓
Digital Match Twin              (shipped for historical matches)
      ↓
Inference Engine                (shipped — validated, leakage-proven)
      ↓
Future Simulation Engine        (next)
      ↓
Decision Intelligence           (first step shipped: What If?)
      ↓
Visual Intelligence             (shipped — replay/TV/analysis layers)
      ↓
API → Web · Mobile · Desktop    (shipped: REST + SDKs + web app)
```

Every future stage obeys the two founding constraints: **deterministic and
reproducible** (same inputs, same outputs, today and in six months) and
**honest** (uncertainty shown, negatives kept, provenance everywhere).
