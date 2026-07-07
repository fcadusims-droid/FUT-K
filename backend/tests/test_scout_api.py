"""Scout AI — season profiles (evolution), similarity, rankings, enrichment.

Offline and deterministic: ingestion uses injected loaders, Wikidata uses an
injected transport. The cross-competition accumulation test is the regression
guard for the old last-ingest-wins bug on global profiles.
"""

from __future__ import annotations

import pytest

from app.ingest import ingest_competition
from app.models import PlayerBio, PlayerProfile, PlayerSeasonProfile
from fie.sources.statsbomb import StatsBombSource

# Player 1 plays in two competitions; player 2 only in the first; player 3
# (a 60+-action creator) only in the second — enough texture for similarity
# and rankings. Volumes are inflated via repeated passes to cross MIN_ACTIONS.


def _events(goals_by_1: int, passes_by: dict) -> list:
    evs = []
    minute = 1
    for _ in range(goals_by_1):
        evs.append({"minute": minute, "second": 0, "type": {"name": "Shot"},
                    "team": {"name": "Alpha"}, "player": {"id": 1, "name": "Striker"},
                    "location": [110, 40], "shot": {"outcome": {"name": "Goal"}}})
        minute += 1
    for pid, (name, team, n) in passes_by.items():
        for _ in range(n):
            evs.append({"minute": minute, "second": 0, "type": {"name": "Pass"},
                        "team": {"name": team}, "player": {"id": pid, "name": name},
                        "location": [40, 40], "pass": {"end_location": [70, 40]}})
            minute += 1
    return evs


def _source(comp: int, season: int, match_id: int, events: list):
    return StatsBombSource(
        comp, season,
        matches_loader=lambda: [{
            "match_id": match_id, "match_date": f"2016-0{season % 9 + 1}-01",
            "home_team": {"home_team_name": "Alpha"},
            "away_team": {"away_team_name": "Beta"},
            "home_score": 1, "away_score": 0,
        }],
        events_loader=lambda mid: events,
    )


@pytest.fixture
def two_competitions(db_session):
    # competition 11: striker scores 3 + 70 passes; teammate 2 makes 80 passes
    ingest_competition(db_session, 11, 27, source=_source(
        11, 27, 555, _events(3, {1: ("Striker", "Alpha", 70),
                                 2: ("Passer", "Alpha", 80)})))
    # competition 43: striker scores 2 more + 65 passes; new creator (id 3)
    ingest_competition(db_session, 43, 3, source=_source(
        43, 3, 777, _events(2, {1: ("Striker", "Alpha", 65),
                                3: ("Creator", "Beta", 90)})))
    return db_session


def test_season_rows_and_cross_competition_accumulation(two_competitions):
    db = two_competitions
    seasons = db.query(PlayerSeasonProfile).filter_by(player_id="1").all()
    assert {(s.competition, s.season) for s in seasons} == {("11", "27"), ("43", "3")}
    assert sum(s.goals for s in seasons) == 5

    # The global profile is the SUM of season rows — the old code would have
    # kept only the last ingest (goals == 2).
    overall = db.get(PlayerProfile, "1")
    assert overall.goals == 5
    assert overall.actions == seasons[0].actions + seasons[1].actions
    assert overall.matches == 2


def test_evolution_endpoint_timeline(client, two_competitions):
    body = client.get("/players/1/evolution").json()
    assert body["name"] == "Striker"
    # Real chronology: ordered by the earliest ingested match date of each
    # competition/season (11/27 -> 2016-01-01, 43/3 -> 2016-04-01).
    assert [(s["competition"], s["season"]) for s in body["seasons"]] == [
        ("11", "27"), ("43", "3")]
    assert body["seasons"][0]["first_match_date"] < body["seasons"][1]["first_match_date"]
    assert body["overall"]["goals"] == 5
    assert body["bio"] is None  # unknown stays unknown
    assert client.get("/players/nobody/evolution").status_code == 404


def test_similar_endpoint_ranks_by_behavior(client, two_competitions):
    body = client.get("/players/1/similar").json()
    assert body["name"] == "Striker"
    ids = [s["player_id"] for s in body["similar"]]
    # the two pure passers resemble each other more than the scorer
    assert set(ids) == {"2", "3"}
    assert "not a potential prediction" in body["note"].lower()

    twin = client.get("/players/2/similar").json()
    assert twin["similar"][0]["player_id"] == "3"  # passer's twin is the creator
    assert client.get("/players/nobody/similar").status_code == 404


def test_rankings_cohort_percentiles_and_age_filter(client, two_competitions, db_session):
    # verified bio for the striker only (a real-shaped record)
    db_session.add(PlayerBio(player_id="1", name="Striker", birth_date="2008-03-01",
                             height_cm=180, position="striker", citizenship="Brazil",
                             qid="Q1", source="wikidata", fetched_at="2026-07-05"))
    db_session.commit()

    # on_date fixed -> ages (and the whole ranking) are reproducible
    body = client.get("/scout/rankings?limit=10&on_date=2026-07-05").json()
    assert body["cohort_size"] == 3
    top = body["players"][0]
    assert top["player_id"] == "1"           # only scorer -> top attack percentile
    assert top["age"] == 18.34 and top["scout"]["age_factor"] == 1.15
    others = {p["player_id"]: p for p in body["players"][1:]}
    assert all(p["age"] is None and p["scout"]["age_factor"] == 1.0
               for p in others.values())     # unknown age -> neutral, never guessed

    # age filter: only the player with a VERIFIED birth date survives
    young = client.get("/scout/rankings?max_age=21&on_date=2026-07-05").json()
    assert [p["player_id"] for p in young["players"]] == ["1"]

    # season-scoped cohort
    comp43 = client.get("/scout/rankings?competition=43&season=3").json()
    assert {p["player_id"] for p in comp43["players"]} == {"1", "3"}


def test_enrich_bios_skips_existing_and_never_guesses(db_session, two_competitions):
    import pathlib
    import sys

    # Absolute path: the app workflow runs pytest from the repo root, the
    # backend workflow from backend/ — a CWD-relative "scripts" breaks one.
    scripts_dir = str(pathlib.Path(__file__).resolve().parents[1] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from enrich_bios import enrich
    from fie.sources.wikidata import WikidataSource

    calls = []

    def http_get(url):
        calls.append(url)
        if "wbsearchentities" in url:
            if "Striker" in url:
                return {"search": [{"id": "Q77"}]}
            return {"search": []}  # nobody else matches -> stays unknown
        return {"entities": {"Q77": {"claims": {
            "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q937857"}}}}],
            "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+2006-03-01T00:00:00Z"}}}}],
        }}}}

    src = WikidataSource(http_get=http_get)
    r1 = enrich(db_session, src, min_actions=60, limit=None, refresh=False)
    assert r1["enriched"] == 1 and r1["unmatched"] == 2
    bio = db_session.get(PlayerBio, "1")
    assert bio.birth_date == "2006-03-01" and bio.qid == "Q77"
    assert db_session.get(PlayerBio, "2") is None   # no row, not a guess

    # second run: the enriched player is skipped entirely (dedup)
    n = len(calls)
    r2 = enrich(db_session, src, min_actions=60, limit=None, refresh=False)
    assert r2["enriched"] == 0
    striker_lookups = [u for u in calls[n:] if "Striker" in u]
    assert striker_lookups == []


def test_refresh_pair_keeps_profiles_in_step(db_session):
    """refresh_pair used to add matches but never touch profiles; now the
    season accumulation is rebuilt over every match of the pair."""
    from app.learningloop import refresh_pair

    m1 = {"match_id": 901, "match_date": "2016-01-01",
          "home_team": {"home_team_name": "Alpha"},
          "away_team": {"away_team_name": "Beta"}, "home_score": 1, "away_score": 0}
    m2 = {**m1, "match_id": 902, "match_date": "2016-02-01"}
    ev1 = _events(1, {1: ("Striker", "Alpha", 70)})
    ev2 = _events(2, {1: ("Striker", "Alpha", 70)})

    # first: only match 901 exists upstream -> profile sees 1 goal
    src1 = StatsBombSource(99, 9, matches_loader=lambda: [m1],
                           events_loader=lambda mid: ev1)
    ingest_competition(db_session, 99, 9, source=src1)
    assert db_session.get(PlayerProfile, "1").goals == 1

    # later: upstream now has match 902 too; refresh adds ONLY the new match
    # and the profiles follow (3 goals across both, matches == 2)
    src2 = StatsBombSource(99, 9, matches_loader=lambda: [m1, m2],
                           events_loader=lambda mid: ev1 if str(mid) == "901" else ev2)
    run = refresh_pair(db_session, 99, 9, source=src2)
    assert run.matches_added == 1 and run.matches_skipped == 1
    prof = db_session.get(PlayerProfile, "1")
    assert prof.goals == 3 and prof.matches == 2
    season = db_session.get(PlayerSeasonProfile, ("1", "99", "9"))
    assert season.goals == 3
