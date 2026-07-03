# FUT-K — Product definition

## Identity

**FUT-K is the match intelligence terminal** — the Bloomberg Terminal of
football. Not a stats site, not a betting tool: the place where you open a
match and *understand* it — what is happening, why, and what is likely next —
in plain language, backed by a validated engine.

One sentence: **"Open any match. Understand it like a professional analyst."**

## Personas (one engine, different products)

| Persona | Wants | FUT-K surface |
|---|---|---|
| **Analyst** (primary, v1) | the mechanism: momentum, pressure, regimes, calibrated probabilities | **Analyst mode** — the full panel, charts, raw metrics |
| **Journalist / storyteller** (secondary, v1) | the story: turning points, who changed the game, quotable lines | **Match Story** — the narrated timeline |
| Fan | to follow a match and get honest "what's likely" | default humanized view (no jargon) |
| Coach / club | opponent patterns, player DNA, network dependence | Explore + player pages (later) |

Bettors are **not** a target persona: the engine's philosophy is understanding,
not picking winners, and the external benchmark (validation §5.6) is explicit
that we sit below the closing line.

## Interface principles

1. **Humans first, jargon behind a toggle.** The default view never says
   *regime, confidence, consensus, causality*. It says: *"Barcelona is
   dominating territorially. A goal in the next 10 minutes is likely (32%).
   Mostly because of sustained pressure down the left."* Analyst mode exposes
   the raw metrics for those who want them.
2. **Story over dashboard.** A match opens as a narrative — "25' — the game
   changed" — with the panel one tap away. (This is design-doc Section 17,
   Match Memory, made product.)
3. **Signature visuals.** Momentum Timeline, Pressure Index, Regime Timeline,
   Confidence Curve — consistent, branded, honest (uncertainty always shown).
4. **From games to football.** The historical bank answers questions across
   matches — "comebacks from 2 down", "wildest momentum swings" — turning the
   engine into a query system.

## The four modes (product direction)

FUT-K is not a stats site with charts; it is a **digital twin of the match**
you can explore. The slogan: *"Relive any match. Stop time. Ask questions.
Change decisions. See what would have happened."* Four modes, one engine:

| Mode | What it is | Status |
|---|---|---|
| **Replay** | the living 2D pitch: ball gliding between real touchpoints, event pings, goal flashes, speeds 0.25×–32×, TV/standard/analysis views, the engine narrating as the clock runs | ✅ shipped (Replay Engine v1) |
| **Analysis** | layers on top of the replay: activity zones from real event locations, pressure glow, momentum arrow, pause-and-ask ("why?" → the explainability cascade) | ✅ shipped (analysis mode + `why?`) |
| **What If?** | counterfactuals: remove a goal or card and re-run the engine's pure functions from that minute — baseline vs counterfactual, honestly labeled a *re-reading, not a prophecy* | ✅ shipped (`/matches/{id}/whatif` + the What If? card) |
| **Live** | the same pitch fed by live multi-source feeds through the fusion layer | future (needs live sources; design doc Section 4) |

The visual bet is deliberate: **no 3D, no fabricated player positions, no
fake realism**. The brain understands motion better than numbers — so the
replay shows real recorded touchpoints, honest reconstructions between them,
and the engine's validated reading as tint and motion. Value is in the
information, not the render.

## v1 scope (this iteration)

- Humanized default panel + Analyst mode toggle
- Match Story (narrated beats from the replay timeline)
- Regime band + Pressure Index + Confidence Curve charts
- Explore page: preset historical queries over all ingested matches
- **Replay Engine v1**: the 2D pitch replay above, on every ingested match
