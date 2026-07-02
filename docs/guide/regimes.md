# How Regimes work

Football is not one game — it switches between **states**, and the same
statistic means different things in each. FUT-K calls these states *regimes*
and re-reads every number through them.

| Regime | What it means |
|---|---|
| NORMAL | balanced, 11v11, no special urgency |
| PRESSURE | one team is stacking attacks; the other only defends |
| POST_GOAL | the minutes right after a goal — the match is resettling |
| POST_RED_CARD | 11v10 — a structural imbalance |
| DESPERATION | a team trails late and throws everything forward |
| END_GAME | the final minutes — managing or chasing the result |

Why it matters: high pressure in NORMAL suggests a goal is coming — news. High
pressure in DESPERATION is *expected* (the trailing team must push) — not news.
The regime label tells you which lens to read the numbers through.

One honest finding from our validation: the regime's value is
**interpretive**. Adding regime-specific goal-rate multipliers did not improve
predictions out of sample — the base signals already carry that information.
The label is for *you*, the reader, not a secret ingredient of the forecast.
