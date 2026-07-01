"""Synthetic narrative worlds (Part D.2 / D.3).

Ground truth for the credibility- and narrative-memory-convergence tests: a source
whose opinions are correct with a known probability, and a recurring pattern with a
known true confirmation rate.
"""

from __future__ import annotations

import numpy as np


def narrative_world(true_accuracy, n_opinions, seed=None):
    """A source whose opinions are correct with probability ``true_accuracy``.

    Returns a list of ``label`` strings suitable for ``update_credibility`` — a
    "hit" (``"Confirmed"``) with probability ``true_accuracy``, else a miss
    (``"Not confirmed"``).
    """
    rng = np.random.default_rng(seed)
    draws = rng.random(n_opinions) < true_accuracy
    return ["Confirmed" if hit else "Not confirmed" for hit in draws]


def narrative_pattern_world(true_rate, n_games, seed=None):
    """A recurring narrative pattern confirmed with probability ``true_rate``.

    Returns a list of ``bool`` draws suitable for ``update_narrative_memory``.
    """
    rng = np.random.default_rng(seed)
    return [bool(x) for x in (rng.random(n_games) < true_rate)]
