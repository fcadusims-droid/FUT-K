# Interpreting Confidence

Every probability FUT-K shows carries a second number: **confidence** — how
much the engine trusts its own reading right now.

These are different things:

| | Probability | Confidence |
|---|---|---|
| "Goal in next 10 min" | 62% | 91% → a solid read |
| "Goal in next 10 min" | 62% | 28% → a shaky guess |

Same probability, opposite advice. Confidence is **low** when: the match just
changed state (right after a goal or a red card), few events have happened yet
(early minutes), or sources disagree. It is **high** when the picture has been
stable and well-fed for a while.

FUT-K validates confidence itself: over many matches, high-confidence
predictions must err less than low-confidence ones, or the confidence would be
redefined. An unvalidated confidence number is worse than none — it gives false
security.

**Rule of thumb:** treat low-confidence panels as "watch", not "act". The app's
plain-language view does this for you — it softens its own tone ("the picture
is still settling") whenever confidence is low.
