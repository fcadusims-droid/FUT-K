"""Data Fusion Layer on real data: StatsBomb x football-data.co.uk.

Two independent providers describe the same fixtures (Bundesliga 2023/24 —
StatsBomb open data covers Bayer Leverkusen's 34 matches; football-data.co.uk
covers the whole league with scores, corners and cards). This script runs the
deterministic fusion pipeline end to end:

    entity resolution -> match resolution -> field comparison ->
    weighted fusion -> unified records + measured agreement rates

and writes validation/results/RESULTS_FUSION.md. The agreement table is the
empirical starting point for per-source reliability scores.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import urllib.request

from fie.fusion import agreement_report, fuse_match, resolve_matches
from fie.sources.statsbomb import StatsBombSource

FD_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".sb_cache"
)

# Priors: StatsBomb is curated event data (higher); football-data aggregates
# official stats (high, slightly lower for in-match counts). These are inputs
# to the vote, and the *measured* agreement rates below are how they evolve.
PRIORS = {"statsbomb": 0.95, "football_data": 0.90}

FIELDS = {
    "home_goals": 0, "away_goals": 0,
    "corners_home": 0, "corners_away": 0,
    "yellows_home": 0, "yellows_away": 0,
    "reds_home": 0, "reds_away": 0,
}


def _fd_date_to_iso(d: str) -> str:
    day, month, year = d.split("/")
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month}-{day}"


def load_football_data(league: str, season: str, cache_dir: str) -> list:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"fd_{league}_{season}.csv")
    if not os.path.exists(path):
        with urllib.request.urlopen(FD_URL.format(season=season, league=league),
                                    timeout=60) as r:
            data = r.read()
        with open(path, "wb") as fh:
            fh.write(data)
    text = open(path, "rb").read().decode("latin-1")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out.append({
                "date": _fd_date_to_iso(row["Date"]),
                "home": row["HomeTeam"], "away": row["AwayTeam"],
                "home_goals": int(row["FTHG"]), "away_goals": int(row["FTAG"]),
                "corners_home": int(row["HC"]), "corners_away": int(row["AC"]),
                "yellows_home": int(row["HY"]), "yellows_away": int(row["AY"]),
                "reds_home": int(row["HR"]), "reds_away": int(row["AR"]),
            })
        except (KeyError, ValueError):
            continue
    return out


def load_statsbomb(competition: int, season: int, cache_dir: str) -> list:
    source = StatsBombSource(competition, season, cache_dir=cache_dir)
    out = []
    for raw in source.matches():
        mid = raw["match_id"]
        try:
            match = source.match(mid)
        except Exception as exc:  # noqa: BLE001
            print(f"  statsbomb match {mid}: skipped ({exc})")
            continue
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
            "corners_home": counts["corner"]["HOME"],
            "corners_away": counts["corner"]["AWAY"],
            "yellows_home": counts["yellow_card"]["HOME"],
            "yellows_away": counts["yellow_card"]["AWAY"],
            "reds_home": counts["red_card"]["HOME"],
            "reds_away": counts["red_card"]["AWAY"],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sb", default="9/281", help="StatsBomb comp/season")
    ap.add_argument("--fd", default="D1/2324", help="football-data league/season")
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--out", default="validation/results/RESULTS_FUSION.md")
    args = ap.parse_args()

    comp, season = (int(x) for x in args.sb.split("/"))
    league, fd_season = args.fd.split("/")

    print("Loading sources ...")
    sources = {
        "statsbomb": load_statsbomb(comp, season, args.cache),
        "football_data": load_football_data(league, fd_season, args.cache),
    }
    n_sb, n_fd = len(sources["statsbomb"]), len(sources["football_data"])
    resolved = resolve_matches(sources)
    both = [f for f in resolved if len(f["records"]) == 2]
    print(f"statsbomb={n_sb} football_data={n_fd} -> fixtures in both: {len(both)}")

    report = agreement_report(both, FIELDS, PRIORS)
    conflicts = []
    for fixture in both:
        unified = fuse_match(fixture["records"], FIELDS, PRIORS)
        for field in unified["_conflicts"]:
            cell = unified[field]
            conflicts.append(
                f"{fixture['key'][0]} {fixture['key'][1]} vs {fixture['key'][2]} — "
                f"{field}: fused={cell['value']} (conf {cell['confidence']}, "
                f"dissent {cell['dissent']})"
            )

    lines = [
        "# RESULTS (fusion) — Data Fusion Layer on two real providers",
        "",
        f"> Generated by `scripts/fuse_sources.py`. StatsBomb {args.sb} events x "
        f"football-data.co.uk {args.fd} match stats. Deterministic pipeline: "
        "entity resolution -> match resolution -> weighted fusion "
        f"(priors {PRIORS}).",
        "",
        f"- StatsBomb records: **{n_sb}** · football-data records: **{n_fd}**",
        f"- Fixtures resolved as the same match in both sources: "
        f"**{len(both)}/{n_sb}**",
        "",
        "## Measured cross-source agreement",
        "",
        "| Field | Compared | Agreed | Rate |",
        "|---|---|---|---|",
    ]
    for field, s in report.items():
        lines.append(f"| {field} | {s['compared']} | {s['agreed']} | "
                     f"{s['rate'] if s['rate'] is not None else '—'} |")
    lines += ["", f"## Conflicts detected ({len(conflicts)})", ""]
    lines += [f"- {c}" for c in conflicts[:20]] or ["- none"]
    if len(conflicts) > 20:
        lines.append(f"- … and {len(conflicts) - 20} more")
    lines += [
        "",
        "## Reading",
        "",
        "- **Goals should agree ~100%** — both providers watch the same scoreboard; "
        "any goal conflict would indicate an ingestion bug, so this doubles as an "
        "end-to-end data-quality check.",
        "- **Corners/cards agreement measures definitional drift** between an "
        "event-collector (StatsBomb) and an official-stats aggregator "
        "(football-data). Disagreements are *information*: they are exactly the "
        "per-source reliability signal the fusion layer feeds on.",
        "- Every fused field carries provenance (which sources), a confidence "
        "(winning share of prior weight), and recorded dissent — nothing is "
        "silently overwritten.",
        "",
    ]
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines[4:20]))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
