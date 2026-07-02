# Reading the panel

Top to bottom, what the match panel shows:

1. **Score and minute** — the hero number. Everything below describes *this*
   minute, computed only from what had happened by then (never the future).
2. **The plain-language reading** (default view) — who is on top, what state
   the match is in, how likely a goal is soon, and the main reasons. When the
   engine's confidence is low, the text says so.
3. **Analyst mode** — the raw layer:
   - **Regime chip** — the match state (see [Regimes](./regimes.md)).
   - **Confidence** — trust in the current reading (see
     [Confidence](./confidence.md)).
   - **Change score (0–100)** — how far the match has drifted from what was
     expected before kick-off. High = an "off-script" game.
   - **Momentum bar** — each team's share of recent attacking pressure, decayed
     so the last few minutes weigh most.
   - **Prediction meters** — Poisson-based probabilities for the next events;
     each is validated for calibration (when the engine says 30%, it happens
     ~30% of the time over many matches).
   - **Why** — the mechanisms behind the current numbers.
4. **Match Story** — the narrated timeline: goals in context, "the game
   changed" beats, momentum swings. Click any beat to jump the replay there.
5. **Charts** — Momentum Timeline (with goal markers), and in analyst mode the
   Pressure Index and Confidence Curve.
6. **Ask the engine** — questions like "what happened after minute 60?" or
   "why did they lose?", answered deterministically from the engine's own
   reading of the match.
