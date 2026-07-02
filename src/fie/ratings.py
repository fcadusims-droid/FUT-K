"""External-benchmark models: Elo and attack/defense Poisson (stdlib only).

These are the *reference opponents* for the external validation
(validation/README.md §7): classic, well-understood match-outcome models that
FUT-K's numbers can be anchored against, plus helpers to score 1X2 probability
triples and to de-margin bookmaker odds. All models are walk-forward by
construction: they are updated one match at a time, and a prediction for match
*t* only ever uses matches that finished before *t*.
"""

from __future__ import annotations

import math
from collections import defaultdict

OUTCOMES = ("H", "D", "A")  # home win / draw / away win


def outcome_index(home_goals: int, away_goals: int) -> int:
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


# --------------------------------------------------------------------------- #
# Elo (standard, with a home advantage in rating points)
# --------------------------------------------------------------------------- #
class Elo:
    """Classic Elo over match results; draws count as half a win."""

    def __init__(self, k: float = 20.0, home_adv: float = 60.0, base: float = 1500.0):
        self.k = k
        self.home_adv = home_adv
        self.base = base
        self.rating: dict = defaultdict(lambda: base)

    def expected_home(self, home: str, away: str) -> float:
        diff = self.rating[home] + self.home_adv - self.rating[away]
        return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))

    def predict_1x2(self, home: str, away: str, draw_rate: float) -> tuple:
        """1X2 triple: the draw mass comes from the trailing league draw rate,
        the rest is split by the Elo expectation. Simple and documented — not a
        full Davidson draw model."""
        e = self.expected_home(home, away)
        p_d = min(max(draw_rate, 0.0), 0.9)
        return (e * (1 - p_d), p_d, (1 - e) * (1 - p_d))

    def update(self, home: str, away: str, home_goals: int, away_goals: int) -> None:
        e = self.expected_home(home, away)
        score = {0: 1.0, 1: 0.5, 2: 0.0}[outcome_index(home_goals, away_goals)]
        delta = self.k * (score - e)
        self.rating[home] += delta
        self.rating[away] -= delta


# --------------------------------------------------------------------------- #
# Attack/defense Poisson (Dixon-Coles-lite, moment-based with shrinkage)
# --------------------------------------------------------------------------- #
class PoissonAD:
    """Per-team attack/defense multipliers over a league-average Poisson.

    lambda_home = league_home_avg * att[home] * def_[away]
    lambda_away = league_away_avg * att[away] * def_[home]

    Strengths are moment estimates (scored/conceded per match relative to the
    league), shrunk toward 1.0 with a pseudo-count prior so early-season teams
    are not over-trusted. 1X2 probabilities come from an independent-Poisson
    score grid. Updated match by match — walk-forward safe.
    """

    def __init__(self, prior_matches: float = 6.0, max_goals: int = 10):
        self.prior = prior_matches
        self.max_goals = max_goals
        self.scored: dict = defaultdict(float)
        self.conceded: dict = defaultdict(float)
        self.played: dict = defaultdict(int)
        self.total_home_goals = 0.0
        self.total_away_goals = 0.0
        self.total_matches = 0

    def _league_avgs(self) -> tuple:
        if self.total_matches == 0:
            return 1.45, 1.15  # long-run football priors (goals/match, home/away)
        return (
            self.total_home_goals / self.total_matches,
            self.total_away_goals / self.total_matches,
        )

    def _strength(self, per_match: float, played: int, league_avg: float) -> float:
        if league_avg <= 0:
            return 1.0
        raw = per_match / league_avg
        return (raw * played + 1.0 * self.prior) / (played + self.prior)

    def rates(self, home: str, away: str) -> tuple:
        home_avg, away_avg = self._league_avgs()
        overall = (home_avg + away_avg) / 2.0
        att_h = self._strength(
            self.scored[home] / max(1, self.played[home]), self.played[home], overall
        )
        def_a = self._strength(
            self.conceded[away] / max(1, self.played[away]), self.played[away], overall
        )
        att_a = self._strength(
            self.scored[away] / max(1, self.played[away]), self.played[away], overall
        )
        def_h = self._strength(
            self.conceded[home] / max(1, self.played[home]), self.played[home], overall
        )
        return home_avg * att_h * def_a, away_avg * att_a * def_h

    def predict_1x2(self, home: str, away: str) -> tuple:
        lam_h, lam_a = self.rates(home, away)
        ph = [math.exp(-lam_h) * lam_h**i / math.factorial(i) for i in range(self.max_goals + 1)]
        pa = [math.exp(-lam_a) * lam_a**j / math.factorial(j) for j in range(self.max_goals + 1)]
        p_home = p_draw = p_away = 0.0
        for i, pi in enumerate(ph):
            for j, pj in enumerate(pa):
                p = pi * pj
                if i > j:
                    p_home += p
                elif i == j:
                    p_draw += p
                else:
                    p_away += p
        total = p_home + p_draw + p_away  # grid truncation -> renormalize
        return (p_home / total, p_draw / total, p_away / total)

    def update(self, home: str, away: str, home_goals: int, away_goals: int) -> None:
        self.scored[home] += home_goals
        self.conceded[home] += away_goals
        self.scored[away] += away_goals
        self.conceded[away] += home_goals
        self.played[home] += 1
        self.played[away] += 1
        self.total_home_goals += home_goals
        self.total_away_goals += away_goals
        self.total_matches += 1


# --------------------------------------------------------------------------- #
# Baseline + bookmaker helpers, multiclass scoring
# --------------------------------------------------------------------------- #
class TrailingFrequencies:
    """The naive baseline: trailing H/D/A shares (Laplace-smoothed)."""

    def __init__(self):
        self.counts = [1.0, 1.0, 1.0]  # Laplace prior

    def predict_1x2(self) -> tuple:
        total = sum(self.counts)
        return tuple(c / total for c in self.counts)

    @property
    def draw_rate(self) -> float:
        return self.counts[1] / sum(self.counts)

    def update(self, home_goals: int, away_goals: int) -> None:
        self.counts[outcome_index(home_goals, away_goals)] += 1


def implied_1x2(odds_h: float, odds_d: float, odds_a: float) -> tuple:
    """De-margined bookmaker probabilities (proportional normalization)."""
    inv = (1.0 / odds_h, 1.0 / odds_d, 1.0 / odds_a)
    total = sum(inv)
    return tuple(v / total for v in inv)


def brier_multi(probs, outcome_idx: int) -> float:
    """Multiclass Brier: sum over classes of (p_k - y_k)^2."""
    return sum(
        (p - (1.0 if k == outcome_idx else 0.0)) ** 2 for k, p in enumerate(probs)
    )


def logloss_multi(probs, outcome_idx: int, eps: float = 1e-15) -> float:
    return -math.log(max(eps, probs[outcome_idx]))
