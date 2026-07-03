"""What If? — counterfactual replay (the fourth mode).

The panel is a pure function of the event stream, so a counterfactual is
cheap and exact: remove one real event and re-run the same validated engine
over the modified stream. Both timelines are computed by identical code on
identical rules — the only difference is the removed event.

Honesty note, by design: this is **the engine re-reading the match**, not a
prophecy. Removing a goal cannot tell you what players would have done
differently; it tells you how the validated reading (score, momentum decay,
predictions, regimes) depends on that event. The API says so in its payload.
"""

from __future__ import annotations

import math

from .panel import panel_state

# Events worth removing: the discrete facts a viewer would point at.
REMOVABLE = {"goal", "red_card", "yellow_card"}
MATCH_TOLERANCE = 0.6  # minutes: how close the request must point at an event


def find_event(events: list, minute: float, etype: str, team: str):
    """The single event the request points at, or None."""
    candidates = [
        e for e in events
        if e.type == etype and e.team == team
        and abs(e.minute - minute) <= MATCH_TOLERANCE
    ]
    candidates.sort(key=lambda e: abs(e.minute - minute))
    return candidates[0] if candidates else None


def whatif_remove(events: list, minute: float, etype: str, team: str,
                  match_id: str, params=None) -> dict | None:
    """Baseline vs counterfactual panel timelines after removing one event.

    Returns None when no matching event exists. Deterministic: two pure
    replays of the same engine, one with the event and one without.
    """
    target = find_event(events, minute, etype, team)
    if target is None:
        return None
    cf_events = [e for e in events if e is not target]

    duration = math.ceil(max((e.minute for e in events), default=90.0))
    start = max(1, math.floor(target.minute))
    minutes = list(range(start, duration + 1))

    def series(evs: list) -> dict:
        out = {"goal_next_10min": [], "next_goal_home": [], "momentum_home": [],
               "score": []}
        for t in minutes:
            p = panel_state(evs, float(t), match_id=match_id, params=params)
            out["goal_next_10min"].append(round(p["predictions"]["goal_next_10min"], 4))
            out["next_goal_home"].append(round(p["predictions"]["next_goal"]["home"], 4))
            out["momentum_home"].append(round(p["momentum"]["home"], 4))
            out["score"].append([p["score"]["home"], p["score"]["away"]])
        return out

    baseline = series(events)
    counterfactual = series(cf_events)

    max_div = max(
        (abs(a - b) for a, b in zip(baseline["goal_next_10min"],
                                    counterfactual["goal_next_10min"])),
        default=0.0,
    )
    end_b, end_c = baseline["score"][-1], counterfactual["score"][-1]
    swing = (counterfactual["next_goal_home"][-1]
             - baseline["next_goal_home"][-1])
    side = "HOME" if swing > 0 else "AWAY"
    reading = (
        f"Without the {target.minute:.0f}' {etype.replace('_', ' ')} ({team}): "
        f"the engine's full-time reading goes from {end_b[0]}-{end_b[1]} to "
        f"{end_c[0]}-{end_c[1]}; the next-goal balance shifts "
        f"{abs(swing):.0%} toward {side}; the goal probability curve diverges "
        f"up to {max_div:.0%}."
    )
    return {
        "removed": {"minute": target.minute, "type": target.type,
                    "team": target.team},
        "from_minute": start,
        "minutes": minutes,
        "baseline": baseline,
        "counterfactual": counterfactual,
        "reading": reading,
        "note": (
            "A counterfactual is the engine re-reading the match without this "
            "event — the same validated pure functions over a modified stream. "
            "It shows how the reading depends on the event, not what players "
            "would have done differently."
        ),
    }
