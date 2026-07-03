"""Provider loaders for the Data Fusion Layer (Application layer: I/O lives here).

Each loader returns plain match-record dicts (``date``, ``home``, ``away`` +
stat fields) ready for ``fie.fusion.resolve_matches``. Downloads are cached on
disk so every run after the first is offline and byte-reproducible.

Shared by ``scripts/fuse_sources.py`` (the validation report) and
``backend/scripts/ingest_fused.py`` (the production ingestion pipeline).
"""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.request

FD_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
OF_URL = "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{league}.json"

# Priors: StatsBomb is curated event data (higher); football-data aggregates
# official stats; openfootball is community-maintained. These are the *inputs*
# to the vote — `fie.fusion.priors_from_agreement` measures how each source
# actually performs, closing the loop deterministically.
PRIORS = {"statsbomb": 0.95, "football_data": 0.90, "openfootball": 0.80}

FIELDS = {
    "home_goals": 0, "away_goals": 0,
    "ht_home": 0, "ht_away": 0,
    "corners_home": 0, "corners_away": 0,
    "yellows_home": 0, "yellows_away": 0,
    "reds_home": 0, "reds_away": 0,
}

# League presets the fusion pipeline knows how to load. `statsbomb` is None
# where open data has no event coverage — fusion still runs on the other two.
FUSION_LEAGUES = {
    "bundesliga-2324": {
        "label": "Bundesliga 2023/24",
        "statsbomb": (9, 281),
        "football_data": ("D1", "2324"),
        "openfootball": ("2023-24", "de.1"),
    },
    "premier-league-2324": {
        "label": "Premier League 2023/24",
        "statsbomb": None,
        "football_data": ("E0", "2324"),
        "openfootball": ("2023-24", "en.1"),
    },
    "serie-a-2324": {
        "label": "Serie A 2023/24",
        "statsbomb": None,
        "football_data": ("I1", "2324"),
        "openfootball": ("2023-24", "it.1"),
    },
    "ligue-1-2324": {
        "label": "Ligue 1 2023/24",
        "statsbomb": None,
        "football_data": ("F1", "2324"),
        "openfootball": ("2023-24", "fr.1"),
    },
}


def _download(url: str, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    with open(path, "wb") as fh:
        fh.write(data)


def _fd_date_to_iso(d: str) -> str:
    day, month, year = d.split("/")
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month}-{day}"


def load_football_data(league: str, season: str, cache_dir: str) -> list:
    """Official match stats + odds aggregator (football-data.co.uk CSV)."""
    path = os.path.join(cache_dir, f"fd_{league}_{season}.csv")
    _download(FD_URL.format(season=season, league=league), path)
    text = open(path, "rb").read().decode("latin-1")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out.append({
                "date": _fd_date_to_iso(row["Date"]),
                "home": row["HomeTeam"], "away": row["AwayTeam"],
                "home_goals": int(row["FTHG"]), "away_goals": int(row["FTAG"]),
                "ht_home": int(row["HTHG"]), "ht_away": int(row["HTAG"]),
                "corners_home": int(row["HC"]), "corners_away": int(row["AC"]),
                "yellows_home": int(row["HY"]), "yellows_away": int(row["AY"]),
                "reds_home": int(row["HR"]), "reds_away": int(row["AR"]),
            })
        except (KeyError, ValueError):
            continue
    return out


def load_openfootball(season: str, league: str, cache_dir: str) -> list:
    """Community-maintained results (independent provider): FT + HT scores."""
    path = os.path.join(cache_dir, f"of_{league.replace('.', '_')}_{season}.json")
    _download(OF_URL.format(season=season, league=league), path)
    doc = json.load(open(path, encoding="utf-8"))
    matches = doc.get("matches") or [m for r in doc.get("rounds", [])
                                     for m in r["matches"]]
    out = []
    for m in matches:
        score = m.get("score") or {}
        ft = score.get("ft")
        ht = score.get("ht")
        if not ft:
            continue
        out.append({
            "date": m["date"], "home": m["team1"], "away": m["team2"],
            "home_goals": ft[0], "away_goals": ft[1],
            "ht_home": ht[0] if ht else None,
            "ht_away": ht[1] if ht else None,
        })
    return out


def load_statsbomb_records(competition: int, season: int, cache_dir: str) -> list:
    """StatsBomb events reduced to match-level records for fusion.

    Half-time is reconstructed from period-1 events — both Shot->Goal and the
    separate "Own Goal For" events (the blind spot the fusion vote caught; see
    validation/results/RESULTS_FUSION.md).
    """
    from fie.sources.statsbomb import StatsBombSource

    source = StatsBombSource(competition, season, cache_dir=cache_dir)
    out = []
    for raw in source.matches():
        mid = raw["match_id"]
        try:
            match = source.match(mid)
        except Exception as exc:  # noqa: BLE001
            print(f"  statsbomb match {mid}: skipped ({exc})")
            continue
        raw_events = source.raw_events(mid)
        ht = {"HOME": 0, "AWAY": 0}
        home_name = match["home_team"]
        for re_ in raw_events:
            if re_.get("period") != 1:
                continue
            tname = re_.get("team", {}).get("name")
            etype = re_.get("type", {}).get("name")
            if (etype == "Shot"
                    and re_.get("shot", {}).get("outcome", {}).get("name") == "Goal"):
                ht["HOME" if tname == home_name else "AWAY"] += 1
            elif etype == "Own Goal For":
                ht["HOME" if tname == home_name else "AWAY"] += 1
        counts = {"corner": {"HOME": 0, "AWAY": 0},
                  "yellow_card": {"HOME": 0, "AWAY": 0},
                  "red_card": {"HOME": 0, "AWAY": 0}}
        for e in match["events"]:
            if e.type in counts:
                counts[e.type][e.team] += 1
        out.append({
            "date": match.get("match_date"),
            "home": match["home_team"], "away": match["away_team"],
            "home_goals": match.get("home_score"), "away_goals": match.get("away_score"),
            "ht_home": ht["HOME"], "ht_away": ht["AWAY"],
            "corners_home": counts["corner"]["HOME"],
            "corners_away": counts["corner"]["AWAY"],
            "yellows_home": counts["yellow_card"]["HOME"],
            "yellows_away": counts["yellow_card"]["AWAY"],
            "reds_home": counts["red_card"]["HOME"],
            "reds_away": counts["red_card"]["AWAY"],
        })
    return out


def load_league_sources(league_key: str, cache_dir: str) -> dict:
    """All available providers for one league preset: {source_name: [records]}."""
    cfg = FUSION_LEAGUES[league_key]
    sources = {}
    if cfg.get("statsbomb"):
        comp, season = cfg["statsbomb"]
        sources["statsbomb"] = load_statsbomb_records(comp, season, cache_dir)
    fd_league, fd_season = cfg["football_data"]
    sources["football_data"] = load_football_data(fd_league, fd_season, cache_dir)
    of_season, of_league = cfg["openfootball"]
    sources["openfootball"] = load_openfootball(of_season, of_league, cache_dir)
    return sources
