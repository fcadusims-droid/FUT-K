"""Synthetic data generators (Part D).

Built once and reused across the whole suite — the foundation every Monte-Carlo
and convergence test depends on. All generators accept and respect a ``seed`` for
reproducibility.
"""

from .poisson_match import (
    poisson_match,
    simulate_goal_in_window,
    simulate_first_scorer,
    simulate_goals_per_match,
    simulate_on_off_influence,
    goal_window_snapshots,
)
from .narrative_world import narrative_world, narrative_pattern_world
from .regime_scenarios import regime_scenarios
from .league_simulator import league_simulator

__all__ = [
    "poisson_match",
    "simulate_goal_in_window",
    "simulate_first_scorer",
    "simulate_goals_per_match",
    "simulate_on_off_influence",
    "goal_window_snapshots",
    "narrative_world",
    "narrative_pattern_world",
    "regime_scenarios",
    "league_simulator",
]
