"""Strategic Assistant (Inference): evaluate in-match decisions.

The Digital Twin can already project the rest of the match (``fie.simulation``)
and re-read it under a change (``What If?``). This layer combines them into a
decision aid: for a team at minute ``t``, it re-simulates the remaining match
under each candidate approach and ranks them by how they move the team's
**win probability**.

Each approach is expressed as a documented multiplier on the two sides'
calibrated scoring intensities — an honest, transparent model of what
"commit forward" or "sit deeper" does to the game, not a learned oracle. The
output says so: it is *the engine's evaluation under its own model*, a
decision aid, not a guarantee.

Deterministic: every candidate shares the same seed, so the ranking is
reproducible.
"""

from __future__ import annotations

from .prediction import Params
from .simulation import simulate_forward

# Candidate approaches. ``self`` / ``opp`` scale the deciding team's and the
# opponent's per-minute goal intensity. Committing forward creates more of your
# own chances but opens the game (opponent up too); sitting deeper suppresses
# both, the opponent more. These magnitudes are deliberate, documented modelling
# choices — tune them as real substitution/tactic effects are measured.
APPROACHES = {
    "keep": {"label": "Keep the current shape", "self": 1.00, "opp": 1.00},
    "attack": {"label": "Commit forward", "self": 1.35, "opp": 1.18},
    "defend": {"label": "Sit deeper, protect", "self": 0.72, "opp": 0.60},
    "control": {"label": "Slow it down, keep the ball", "self": 0.90, "opp": 0.80},
}


def evaluate_decisions(
    state,
    events,
    params: Params | None = None,
    *,
    team: str,
    horizon_minutes: float,
    n_sims: int = 8000,
    seed: int = 0,
    regime: str | None = None,
) -> dict:
    """Rank candidate approaches for ``team`` by their win-probability delta.

    Returns ``{team, minute, horizon_minutes, baseline, decisions[...]}`` where
    each decision carries the resulting win/draw/loss for the team and the
    change in win probability versus keeping the current shape.
    """
    params = params or Params()
    team = "HOME" if team == "HOME" else "AWAY"

    def win_prob(res: dict) -> float:
        o = res["outcome"]
        return o["home_win"] if team == "HOME" else o["away_win"]

    def loss_prob(res: dict) -> float:
        o = res["outcome"]
        return o["away_win"] if team == "HOME" else o["home_win"]

    results = {}
    for key, appr in APPROACHES.items():
        # self/opp map to (home_mult, away_mult) depending on which side decides.
        mult = ((appr["self"], appr["opp"]) if team == "HOME"
                else (appr["opp"], appr["self"]))
        results[key] = simulate_forward(
            state, events, params, horizon_minutes=horizon_minutes,
            n_sims=n_sims, seed=seed, regime=regime, rate_mult=mult,
        )

    base_win = win_prob(results["keep"])
    decisions = []
    for key, appr in APPROACHES.items():
        res = results[key]
        w = win_prob(res)
        decisions.append({
            "key": key,
            "label": appr["label"],
            "win": round(w, 3),
            "draw": round(res["outcome"]["draw"], 3),
            "loss": round(loss_prob(res), 3),
            "delta_win": round(w - base_win, 3),
            "self_mult": appr["self"],
            "opp_mult": appr["opp"],
        })
    # Best first (largest win-prob gain); "keep" stays as the reference point.
    decisions.sort(key=lambda d: -d["delta_win"])
    best = max(decisions, key=lambda d: d["delta_win"])

    return {
        "team": team,
        "minute": round(state.minute, 2),
        "horizon_minutes": round(max(0.0, horizon_minutes), 2),
        "n_sims": n_sims,
        "seed": seed,
        "baseline_win": round(base_win, 3),
        "recommended": best["key"] if best["delta_win"] > 0.005 else "keep",
        "decisions": decisions,
        "note": (
            "Each approach is re-simulated thousands of times under a "
            "documented, transparent effect on both sides' scoring intensity. "
            "This is the engine's evaluation under its own model — a decision "
            "aid, not a guarantee."
        ),
    }
