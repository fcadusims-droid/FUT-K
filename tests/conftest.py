"""Shared fixtures: fixed RNG seed and default params."""

from __future__ import annotations

import numpy as np
import pytest

from fie.prediction import Params

# The single fixed seed CI uses for reproducibility. The Definition of Done
# (Part H) additionally requires MC/CONVERGENCE tests to pass on several seeds;
# see MULTI_SEEDS below and the parametrized MC tests.
SEED = 20240607
MULTI_SEEDS = (1, 7, 42, 101, 2024)
# The minimum multi-seed set Part H requires for every MC/CONVERGENCE test
# ("at least 3 different random seeds, not just the CI default seed").
SEEDS3 = MULTI_SEEDS[:3]


@pytest.fixture
def seed():
    return SEED


@pytest.fixture
def rng():
    return np.random.default_rng(SEED)


@pytest.fixture
def default_params():
    return Params()
