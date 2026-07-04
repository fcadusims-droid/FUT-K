"""football-data.org — network-gated live smoke (skipped by default).

Hits the *real* keyless football-data.org API to prove the connector parses live
responses. Skipped in CI (no network, and to respect the free rate limit); run
with ``FUTK_LIVE_TESTS=1 pytest tests/test_footballdata_live.py``.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FUTK_LIVE_TESTS") != "1",
    reason="network-gated: set FUTK_LIVE_TESTS=1 to hit the real football-data.org API",
)


def test_keyless_competitions_reachable():
    """The keyless /v4/competitions endpoint returns the documented free-tier
    competitions — real evidence the source is live and free."""
    from fie.sources.footballdata import FootballDataSource

    codes = {c["code"] for c in FootballDataSource().competitions()}
    assert {"BSA", "PL", "CL", "WC", "PD"} <= codes  # Brasileirão + Big-5 anchors


def test_keyless_scoreboard_shape():
    """The keyless /v4/matches scoreboard parses into a list (possibly empty
    off-season) of match objects with the fields the connector reads."""
    from fie.sources.footballdata import FootballDataSource

    matches = FootballDataSource().live_matches()
    assert isinstance(matches, list)
    for m in matches[:5]:
        assert "status" in m and "homeTeam" in m and "score" in m
