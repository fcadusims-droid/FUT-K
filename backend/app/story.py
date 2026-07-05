"""Humanized language + the Match Story (product levels 3-4).

Turns the engine's technical state into sentences a fan can read, and a match's
replay timeline into narrated story beats — design-doc Section 17 (Match
Memory) made product. The engine still speaks in regimes and lambdas; this
layer translates. HOME/AWAY are replaced by real team names by the caller.
"""

from __future__ import annotations

REGIME_PHRASES = {
    "NORMAL": "The game is balanced",
    "PRESSURE": "{dom} is piling on the pressure",
    "POST_GOAL": "The match is resettling after the goal",
    "POST_RED_CARD": "The red card has reshaped the game",
    "DESPERATION": "{trail} is chasing the game",
    "END_GAME": "The finale — every ball matters",
}


def humanize_panel(panel: dict, home: str, away: str) -> dict:
    """A plain-language reading of one panel state (no jargon)."""
    mom = panel["momentum"]["home"]
    dom, dom_share = (home, mom) if mom >= 0.5 else (away, 1 - mom)
    score = panel["score"]
    trail = away if score["home"] > score["away"] else home

    if dom_share > 0.72:
        control = f"{dom} is dominating territorially ({dom_share:.0%} of recent momentum)."
    elif dom_share > 0.58:
        control = f"{dom} has the upper hand right now."
    else:
        control = "Neither side is on top — the game is in the balance."

    situation = REGIME_PHRASES.get(panel["regime"], "").format(dom=dom, trail=trail)

    p10 = panel["predictions"]["goal_next_10min"]
    if p10 >= 0.45:
        goal_line = f"A goal feels close — {p10:.0%} chance in the next 10 minutes."
    elif p10 >= 0.25:
        goal_line = f"A goal in the next 10 minutes is plausible ({p10:.0%})."
    else:
        goal_line = f"A quiet spell is more likely — only {p10:.0%} chance of a goal soon."

    next_goal = panel["predictions"]["next_goal"]
    favored, fav_p = (home, next_goal["home"]) if next_goal["home"] >= 0.5 else (away, next_goal["away"])
    reasons = [
        line.replace("✓ ", "").replace("HOME", home).replace("AWAY", away)
        for line in panel["explanation"]["because"]
        if not line.startswith("the game shifted")
    ]

    hedged = bool(panel["explanation"]["note"])
    return {
        "control": control,
        "situation": situation,
        "goal_outlook": goal_line,
        "next_goal": f"If a goal comes, it favors {favored} ({fav_p:.0%}).",
        "reasons": reasons,
        "hedged": hedged,  # low engine confidence -> the UI softens the tone
    }


def transition_beat(prev: dict, panel: dict, home: str, away: str,
                    goal_set=frozenset()) -> dict | None:
    """The single story beat for one state -> state transition, or ``None``.

    The shared kernel of both the post-match story and Live Mode's insights:
    given two consecutive panel states it detects, in priority order, a goal
    (score change), a regime shift that isn't just a goal echo, or a wide
    momentum handover. Pure and deterministic — every beat traces to a real
    change in the engine's reading, nothing invented.
    """
    minute = round(panel["minute"])

    # Goals (attributed via the score change).
    dh = panel["score"]["home"] - prev["score"]["home"]
    da = panel["score"]["away"] - prev["score"]["away"]
    if dh or da:
        scorer = home if dh else away
        return {
            "minute": minute,
            "headline": f"Goal — {scorer}",
            "detail": f"{panel['score']['home']}–{panel['score']['away']}. "
                      + humanize_panel(panel, home, away)["control"],
        }

    # Regime shifts that aren't just the goal echo.
    if panel["regime"] != prev["regime"] and minute not in goal_set:
        mom = panel["momentum"]["home"]
        dom = home if mom >= 0.5 else away
        phrase = REGIME_PHRASES.get(panel["regime"], "The pattern changed")
        return {
            "minute": minute,
            "headline": "The game changed",
            "detail": phrase.format(dom=dom, trail=dom) + ".",
        }

    # Momentum handover: control crossed sides by a wide margin.
    if (prev["momentum"]["home"] - 0.5) * (panel["momentum"]["home"] - 0.5) < 0 \
            and abs(panel["momentum"]["home"] - 0.5) > 0.2:
        dom = home if panel["momentum"]["home"] > 0.5 else away
        return {
            "minute": minute,
            "headline": "Momentum swings",
            "detail": f"{dom} has taken control of the match.",
        }
    return None


def match_story(timeline: list, goal_minutes: list, home: str, away: str) -> list:
    """Narrated story beats from the replay timeline (Section 17 as product).

    Beats: kickoff, every goal (with the score after it), every regime change
    that *isn't* a goal echo, and large momentum handovers.
    """
    beats = []
    if not timeline:
        return beats

    beats.append({"minute": 0, "headline": "Kick-off",
                  "detail": f"{home} vs {away}."})

    goal_set = {round(g["minute"]) for g in goal_minutes}
    prev = timeline[0]
    for panel in timeline[1:]:
        beat = transition_beat(prev, panel, home, away, goal_set)
        if beat is not None:
            beats.append(beat)
        prev = panel

    final = timeline[-1]
    beats.append({
        "minute": round(final["minute"]),
        "headline": "Full time",
        "detail": f"Final score {final['score']['home']}–{final['score']['away']}.",
    })
    return beats
