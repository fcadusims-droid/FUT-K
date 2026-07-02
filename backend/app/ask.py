"""Conversational layer (product level 8) — deterministic Q&A over the engine.

No language model: questions are parsed into intents by pattern, and every
answer is assembled from engine outputs (story beats, panels, events). Honest by
construction — the layer can only say what the engine actually knows, and says
so when it can't. English questions; team names matched by substring.
"""

from __future__ import annotations

import re


def _team_side(question: str, home: str, away: str):
    q = question.lower()
    for side, name in (("HOME", home), ("AWAY", away)):
        for token in (name or "").lower().split():
            if len(token) > 3 and token in q:
                return side, name
    return None, None


def _fmt_beats(beats) -> str:
    return " ".join(f"{b['minute']}' {b['headline']}: {b['detail']}" for b in beats)


def answer(question: str, ctx: dict) -> dict:
    """Answer one question about a match.

    ``ctx``: {home, away, story (beats), events (Event list),
    final (h, a), timeline_last (final panel)}.
    """
    q = question.lower().strip()
    home, away = ctx["home"], ctx["away"]
    story = ctx["story"]
    fh, fa = ctx["final"]

    # "what happened after/before minute X" / "between X and Y"
    rng = re.search(r"between\s+(?:minute\s+)?(\d+)\s+and\s+(\d+)", q)
    aft = re.search(r"after\s+(?:the\s+)?(?:minute\s+)?(\d+)", q)
    bef = re.search(r"before\s+(?:the\s+)?(?:minute\s+)?(\d+)", q)
    if rng or aft or bef:
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(2))
        elif aft:
            lo, hi = int(aft.group(1)), 200
        else:
            lo, hi = 0, int(bef.group(1))
        beats = [b for b in story if lo <= b["minute"] <= hi
                 and b["headline"] not in ("Kick-off",)]
        if not beats:
            return {"answer": f"Nothing notable between minute {lo} and {hi} — "
                              "no goals, no regime changes, no momentum swings.",
                    "intent": "window"}
        return {"answer": _fmt_beats(beats), "intent": "window"}

    # "why did X lose/win"
    if "why" in q and ("lose" in q or "lost" in q or "win" in q or "won" in q):
        side, name = _team_side(q, home, away)
        if not side:
            return {"answer": f"Which team do you mean — {home} or {away}?",
                    "intent": "why_result"}
        team_goals, opp_goals = (fh, fa) if side == "HOME" else (fa, fh)
        goals_beats = [b for b in story if b["headline"].startswith("Goal")]
        swings = [b for b in story if b["headline"] in ("Momentum swings", "The game changed")]
        outcome = "won" if team_goals > opp_goals else ("lost" if team_goals < opp_goals else "drew")
        parts = [f"{name} {outcome} {max(fh,fa)}–{min(fh,fa)}." if outcome != "drew"
                 else f"{name} drew {fh}–{fa}."]
        if goals_beats:
            parts.append("The goals: " + _fmt_beats(goals_beats))
        if swings:
            parts.append("The turning points: " + _fmt_beats(swings[:3]))
        return {"answer": " ".join(parts), "intent": "why_result"}

    # referee / cards
    if "referee" in q or "card" in q:
        cards = [(e.minute, e.team, e.type) for e in ctx["events"]
                 if e.type in ("yellow_card", "red_card")]
        if not cards:
            return {"answer": "No cards were shown in this match.", "intent": "cards"}
        reds = [c for c in cards if c[2] == "red_card"]
        names = {"HOME": home, "AWAY": away}
        lines = ", ".join(f"{int(m)}' {'red' if t == 'red_card' else 'yellow'} for {names[s]}"
                          for m, s, t in cards)
        verdict = (" The red card structurally changed the game." if reds
                   else " No red cards — discipline did not decide this match.")
        return {"answer": f"Cards: {lines}.{verdict}", "intent": "cards"}

    # who controlled / dominated
    if "control" in q or "dominat" in q or "better team" in q:
        final_panel = ctx["timeline_last"]
        mom = final_panel["momentum"]["home"]
        dom, share = (home, mom) if mom >= 0.5 else (away, 1 - mom)
        return {"answer": f"Over the closing stretch {dom} held {share:.0%} of the "
                          f"momentum. Final score {fh}–{fa}.", "intent": "control"}

    # what changed / turning point
    if "changed" in q or "turning" in q:
        swings = [b for b in story
                  if b["headline"] in ("The game changed", "Momentum swings")]
        if not swings:
            return {"answer": "The match never really changed character.",
                    "intent": "changes"}
        return {"answer": _fmt_beats(swings), "intent": "changes"}

    return {
        "answer": "I can answer: what happened after/before/between minutes; "
                  "why a team lost or won; whether cards/the referee changed the "
                  "game; who controlled the match; and what the turning points "
                  "were.",
        "intent": "help",
    }
