"""League simulator (Part D.5).

Wraps ``poisson_match`` to produce a whole synthetic season, with per-match lambda
drawn from a realistic distribution (not all matches identical) — needed wherever
a single match is not enough signal (calibration, learning).
"""

from __future__ import annotations

import numpy as np

from .poisson_match import poisson_match


def league_simulator(n_matches, base_rate, seed=None, duration=90, spread=0.4):
    """A list of synthetic matches with per-team lambda varying around ``base_rate``.

    Each team's lambda is ``base_rate * U(1-spread, 1+spread)``, so the season has
    a realistic mix of high- and low-scoring games. Returns match dicts (as from
    ``poisson_match``) with an added ``lambda_home`` / ``lambda_away`` for tests
    that need the ground-truth rate.
    """
    rng = np.random.default_rng(seed)
    matches = []
    for i in range(n_matches):
        lam_home = base_rate * rng.uniform(1 - spread, 1 + spread)
        lam_away = base_rate * rng.uniform(1 - spread, 1 + spread)
        child_seed = int(rng.integers(0, 2**32 - 1))
        match = poisson_match(
            lam_home, lam_away, duration=duration, seed=child_seed, match_id=f"m{i}"
        )
        match["lambda_home"] = lam_home
        match["lambda_away"] = lam_away
        matches.append(match)
    return matches
