"""Future Simulation Engine (Inference): thousands of futures from now.

The design doc's prospective-intelligence idea, made concrete. From the state
at minute ``t`` the engine runs many seeded Monte-Carlo forward simulations of
the remaining match, sampling goals per team from the *validated, calibrated*
per-minute rates (``fie.prediction.rates`` — the same machinery scored on real
data in validation §5). It reports the distribution of what can happen and the
**opportunity windows**: the lanes and short time slices where the next chance
is most likely to form.

Two founding constraints hold here as everywhere:

* **Deterministic.** A fixed ``seed`` makes 10,000 simulations reproducible —
  same state, same seed, same output today and in six months. No wall-clock,
  no unseeded randomness.
* **Honest.** The horizon is **not** a hardcoded 90: the caller passes the
  match's real remaining time, derived from data (period/Half-End markers,
  cross-checked by the fusion layer). The engine never simulates past the real
  end of the match, and never claims certainty — it reports probabilities and
  says so.

No I/O, no LLMs. Pure function of ``(state, events, params, horizon)``.
"""

from __future__ import annotations

import math
import random

from .indices import time_weight
from .prediction import Params, rates

# Attacking actions that mark where a team is trying to hurt the opponent —
# the substrate for lane (left/central/right) opportunity detection.
_ATTACK_TYPES = {"shot", "shot_on_target", "goal", "corner"}

# StatsBomb-frame width lanes (normalized 0-100 y-axis, acting team's attack).
LANES = ("left", "central", "right")


def _lane(y: float) -> str:
    if y >= 66.667:
        return "left"
    if y < 33.333:
        return "right"
    return "central"


def lane_weights(events, team: str, minute: float, tau: float) -> dict:
    """Decay-weighted share of ``team``'s recent attacking actions per lane.

    Reads real event locations only; returns ``{lane: share}`` summing to 1
    (uniform prior when the team has no located attacking actions yet).
    """
    w = {lane: 0.0 for lane in LANES}
    for ev in events:
        if (ev.team == team and ev.minute <= minute
                and ev.type in _ATTACK_TYPES and getattr(ev, "y", None) is not None):
            w[_lane(ev.y)] += time_weight(minute, ev.minute, tau)
    total = sum(w.values())
    if total == 0:
        return {lane: 1 / 3 for lane in LANES}
    return {lane: round(v / total, 4) for lane, v in w.items()}


def simulate_forward(
    state,
    events,
    params: Params | None = None,
    *,
    horizon_minutes: float,
    n_sims: int = 10000,
    seed: int = 0,
    regime: str | None = None,
    profiles: dict | None = None,
    step_seconds: float = 15.0,
    rate_mult: tuple = (1.0, 1.0),
) -> dict:
    """Monte-Carlo projection of the remaining match from ``state.minute``.

    ``horizon_minutes`` is the real time left, supplied by the caller from
    match data — never assumed. Returns the outcome distribution over that
    horizon plus per-lane opportunity windows. Deterministic given ``seed``.

    ``rate_mult`` scales ``(lambda_home, lambda_away)`` after they are computed
    — the honest hook the Strategic Assistant uses to model a decision's effect
    on each side's scoring intensity (1.0 = no change).
    """
    params = params or Params()
    horizon = max(0.0, float(horizon_minutes))
    lam_home, lam_away = rates(state, events, params, regime, profiles)  # per minute
    lam_home *= rate_mult[0]
    lam_away *= rate_mult[1]
    lw = {
        "HOME": lane_weights(events, "HOME", state.minute, params.tau),
        "AWAY": lane_weights(events, "AWAY", state.minute, params.tau),
    }

    if horizon <= 0 or n_sims <= 0:
        return {
            "minute": round(state.minute, 2),
            "horizon_minutes": round(horizon, 2),
            "n_sims": n_sims,
            "seed": seed,
            "goal_prob": {"home": 0.0, "away": 0.0, "any": 0.0},
            "expected_goals": {"home": 0.0, "away": 0.0},
            "outcome": {
                "home_win": 1.0 if state.home_goals > state.away_goals else 0.0,
                "draw": 1.0 if state.home_goals == state.away_goals else 0.0,
                "away_win": 1.0 if state.away_goals > state.home_goals else 0.0,
            },
            "scorelines": [],
            "opportunity_windows": [],
            "note": "no real time remaining — nothing left to simulate",
        }

    step_min = step_seconds / 60.0
    n_steps = max(1, math.ceil(horizon / step_min))
    p_home = lam_home * step_min      # expected goals per step (small -> ~Poisson)
    p_away = lam_away * step_min

    rng = random.Random(seed)
    home_goals_tot = away_goals_tot = 0
    any_goal = home_any = away_any = 0
    # Final-outcome tally from the CURRENT score + simulated remaining goals.
    now_h, now_a = state.home_goals, state.away_goals
    win_home = draw = win_away = 0
    scoreline_counts: dict = {}
    # Per-lane, per-team hazard accumulation over the horizon, and the earliest
    # step where a chance is likely (for the "window").
    lane_hits = {t: {lane: 0 for lane in LANES} for t in ("HOME", "AWAY")}
    first_chance_step = {t: {lane: [] for lane in LANES} for t in ("HOME", "AWAY")}

    for _ in range(n_sims):
        h = a = 0
        seen_first = {t: {lane: False for lane in LANES} for t in ("HOME", "AWAY")}
        for s in range(n_steps):
            for team, p, goals_ref in (("HOME", p_home, "h"), ("AWAY", p_away, "a")):
                if rng.random() < p:
                    if team == "HOME":
                        h += 1
                    else:
                        a += 1
                    # attribute the chance to a lane by the team's real tendency
                    r = rng.random()
                    cum = 0.0
                    chosen = LANES[-1]
                    for lane in LANES:
                        cum += lw[team][lane]
                        if r <= cum:
                            chosen = lane
                            break
                    lane_hits[team][chosen] += 1
                    if not seen_first[team][chosen]:
                        seen_first[team][chosen] = True
                        first_chance_step[team][chosen].append(s)
        home_goals_tot += h
        away_goals_tot += a
        if h + a > 0:
            any_goal += 1
        if h > 0:
            home_any += 1
        if a > 0:
            away_any += 1
        final_h, final_a = now_h + h, now_a + a
        if final_h > final_a:
            win_home += 1
        elif final_h < final_a:
            win_away += 1
        else:
            draw += 1
        key = f"{h}-{a}"
        scoreline_counts[key] = scoreline_counts.get(key, 0) + 1

    # Opportunity windows: for each team+lane, probability a chance forms in the
    # horizon and the median lead-time to the first one (seconds from now).
    windows = []
    for team in ("HOME", "AWAY"):
        for lane in LANES:
            firsts = first_chance_step[team][lane]
            prob = len(firsts) / n_sims
            if prob < 0.05:
                continue
            firsts_sorted = sorted(firsts)
            med = firsts_sorted[len(firsts_sorted) // 2]
            windows.append({
                "team": team,
                "lane": lane,
                "probability": round(prob, 3),
                "eta_seconds": round(med * step_seconds, 1),
                "window_seconds": round(step_seconds, 1),
            })
    windows.sort(key=lambda w: (-w["probability"], w["eta_seconds"]))

    scorelines = sorted(
        ({"score": k, "prob": round(v / n_sims, 3)} for k, v in scoreline_counts.items()),
        key=lambda d: -d["prob"],
    )[:6]

    return {
        "minute": round(state.minute, 2),
        "horizon_minutes": round(horizon, 2),
        "n_sims": n_sims,
        "seed": seed,
        "lambda_per_min": {"home": round(lam_home, 4), "away": round(lam_away, 4)},
        "lane_tendency": lw,
        "goal_prob": {
            "home": round(home_any / n_sims, 3),
            "away": round(away_any / n_sims, 3),
            "any": round(any_goal / n_sims, 3),
        },
        "expected_goals": {
            "home": round(home_goals_tot / n_sims, 3),
            "away": round(away_goals_tot / n_sims, 3),
        },
        "outcome": {
            "home_win": round(win_home / n_sims, 3),
            "draw": round(draw / n_sims, 3),
            "away_win": round(win_away / n_sims, 3),
        },
        "scorelines": scorelines,
        "opportunity_windows": windows,
        "note": (
            "Thousands of seeded forward simulations from calibrated goal "
            "rates, bounded by the match's real remaining time. Probabilities, "
            "not prophecy; lanes reflect where this team has recently attacked."
        ),
    }
