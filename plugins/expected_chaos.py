"""Expected Chaos — the reference FUT-K plugin.

How *wild* was (or is) this match? A bounded 0..1 blend of lead changes, late
goals, red cards, goal volume and momentum turbulence — computed purely from
Core features. This file is the proof of the plugin contract: a brand-new
metric, served by the API and the app, with zero edits to the engine.
"""

from fie.indices import momentum_index
from fie.plugins import match_metric

CHECKPOINTS = (15.0, 30.0, 45.0, 60.0, 75.0, 90.0)


@match_metric("expected_chaos", "How wild the match is, 0..1 (lead swings, late goals, turbulence)")
def expected_chaos(events, params):
    goals = sorted(
        ((e.minute, e.team) for e in events if e.type == "goal"), key=lambda g: g[0]
    )

    # Lead changes and ties broken.
    h = a = leader = changes = 0
    for _, team in goals:
        h += team == "HOME"
        a += team == "AWAY"
        now = (h > a) - (h < a)
        if now != leader and now != 0:
            changes += 1
        leader = now

    late_goals = sum(1 for m, _ in goals if m >= 80)
    reds = sum(1 for e in events if e.type == "red_card")

    # Momentum turbulence: mean absolute swing between checkpoints.
    curve = [
        momentum_index([e for e in events if e.minute <= t], t, params.tau)
        for t in CHECKPOINTS
    ]
    turbulence = sum(abs(b - x) for x, b in zip(curve, curve[1:])) / (len(curve) - 1)

    value = min(1.0, 0.25 * min(changes / 2, 1.0)
                + 0.20 * min(late_goals / 2, 1.0)
                + 0.15 * min(reds / 1, 1.0)
                + 0.20 * min(len(goals) / 6, 1.0)
                + 0.20 * min(turbulence / 0.25, 1.0))

    if value >= 0.7:
        label = "A wild one"
    elif value >= 0.4:
        label = "Lively"
    else:
        label = "Controlled"
    return {
        "value": round(value, 3),
        "summary": f"{label}: {len(goals)} goals, {changes} lead change(s), "
                   f"{late_goals} late goal(s), {reds} red card(s).",
        "components": {
            "lead_changes": changes, "late_goals": late_goals, "red_cards": reds,
            "total_goals": len(goals), "momentum_turbulence": round(turbulence, 3),
        },
    }
