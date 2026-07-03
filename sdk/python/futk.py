"""FUT-K Python SDK — a thin, dependency-free client for the FUT-K API.

Usage:
    from futk import FutK

    fk = FutK("http://localhost:8000")
    for m in fk.matches(competition="43"):
        print(m["home_team"], "vs", m["away_team"])

    panel = fk.state("7525", minute=43)
    print(panel["predictions"]["goal_next_10min"])

    print(fk.ask("7525", "why did Saudi Arabia lose?")["answer"])

Standard library only (urllib). Copyright (c) 2026 João Vitor Perazzolo
(Johnny Kestler). AGPL-3.0 — see the repository LICENSE.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

__version__ = "0.1.0"


class FutK:
    """Client for a running FUT-K backend."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, **params):
        query = {k: v for k, v in params.items() if v is not None}
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    # -- matches ---------------------------------------------------------- #
    def matches(self, competition: str | None = None) -> list:
        return self._get("/matches", competition=competition)

    def match(self, match_id: str) -> dict:
        return self._get(f"/matches/{match_id}")

    def state(self, match_id: str, minute: float) -> dict:
        """The intelligent panel at one minute (leakage-safe)."""
        return self._get(f"/matches/{match_id}/state", minute=minute)

    def state_human(self, match_id: str, minute: float) -> dict:
        """The panel in plain language + the raw panel."""
        return self._get(f"/matches/{match_id}/state/human", minute=minute)

    def timeline(self, match_id: str, step: int = 5) -> list:
        return self._get(f"/matches/{match_id}/timeline", step=step)

    def story(self, match_id: str) -> list:
        """The narrated Match Story."""
        return self._get(f"/matches/{match_id}/story")

    def events(self, match_id: str) -> list:
        """Normalized events with real pitch coordinates (2D replay data)."""
        return self._get(f"/matches/{match_id}/events")

    def fusion_records(self, team: str | None = None, league: str | None = None,
                       conflicts_only: bool = False) -> list:
        """Cross-provider fused match records with per-field provenance."""
        return self._get("/fusion/records", team=team, league=league,
                         conflicts_only=conflicts_only or None)

    def network(self, match_id: str, side: str = "HOME") -> dict:
        """The team's passing network for the match."""
        return self._get(f"/matches/{match_id}/network", side=side)

    def similar(self, match_id: str, limit: int = 5) -> list:
        """Matches whose dynamics felt like this one (semantic search)."""
        return self._get(f"/matches/{match_id}/similar", limit=limit)

    def ask(self, match_id: str, question: str) -> dict:
        """Deterministic Q&A over the engine."""
        return self._get(f"/matches/{match_id}/ask", q=question)

    def explain(self, match_id: str, minute: float) -> dict:
        """Structured explanation cascade: claim -> because -> reliability."""
        return self._get(f"/matches/{match_id}/explain", minute=minute)

    # -- cross-match ------------------------------------------------------ #
    def search(self, query: str) -> list:
        return self._get("/search", q=query)

    def insights(self, preset: str, team: str | None = None) -> list:
        return self._get(f"/insights/{preset}", team=team)

    def insight_presets(self) -> dict:
        return self._get("/insights/presets")

    def team_evolution(self, team: str, competition: str | None = None) -> dict:
        return self._get(f"/teams/{team}/evolution", competition=competition)

    def player_profiles(self, team: str | None = None, archetype: str | None = None,
                        min_actions: int = 0) -> list:
        return self._get("/players/profiles", team=team, archetype=archetype,
                         min_actions=min_actions or None)

    def benchmarks(self) -> list:
        return self._get("/benchmarks")
