# Data sources — free live & historical football data

This is the **measured** research behind FUT-K's data layer: which sources from
[`Guide_to_Football_Soccer_data_and_APIs.md`](../Guide_to_Football_Soccer_data_and_APIs.md)
are actually reachable and free today, what each one really provides, and which
one drives the **live feed**. Every claim here was probed against the live
endpoint (2026-07); nothing is assumed.

FUT-K's honesty rule applies to data too: a connector maps exactly what a
provider reports and **invents nothing**. Where a free feed is coarser than
event-grade data, that limit is stated, not papered over.

## Summary

| Source | Reachable | Free tier | Granularity | Live? | Role in FUT-K |
|---|---|---|---|---|---|
| **football-data.org** (v4) | ✅ 200 | keyless (rate-limited) **+** free API key | match/aggregate: goals, cards, subs (minutes) | ✅ | **live feed** — `fie.sources.footballdata` |
| **StatsBomb Open Data** | ✅ 200 | fully free | event-level: shots/passes/xy/xg | ❌ (historical) | primary history + player DNA (shipped) |
| **openfootball** (football.json) | ✅ 200 | public domain | results only (scores) | ❌ | optional historical results backfill |
| **football-data.co.uk** | ✅ | free CSV | match stats + odds | ❌ | cross-provider fusion anchor (shipped) |
| ScoreBat video API (v3) | ✅ but **deprecated** | free | video highlights only | ✅ (videos) | not used — no event data |
| Mashape-hosted APIs (Sports Open Data, Betlines Ninja, API-Football *legacy*) | ❌ | — | — | — | dead (RapidAPI/Mashape migration) |
| openfooty | ❌ (no keys issued) | — | — | — | not viable |
| Opta / Prozone / Sportmonks / SPAPI / Soccer's API / GoalServe | n/a | paid only | event-grade | ✅ | out of scope (commercial) |

## The live feed: football-data.org

[football-data.org](https://www.football-data.org/) is a real, actively-maintained
REST API and the only **free, live-capable** source in the guide. Measured access:

- **Keyless** (≈10 req/min): `GET /v4/competitions` and `GET /v4/matches`
  (today's live scoreboard — score, status, minute, teams) return `200`.
- **Free API key** (`X-Auth-Token`, register for free): unlocks match **detail**
  (`GET /v4/matches/{id}` with `goals`, `bookings`, `substitutions` arrays,
  each carrying a real minute) and historical/competition queries. Keyless
  requests to those endpoints return `403`.
- **Free-tier competitions (12):** Brasileirão (`BSA`), Premier League (`PL`),
  La Liga (`PD`), Bundesliga (`BL1`), Serie A (`SA`), Ligue 1 (`FL1`),
  Eredivisie (`DED`), Primeira Liga (`PPL`), Championship (`ELC`), Champions
  League (`CL`), European Championship (`EC`), World Cup (`WC`).

**Honest limitation.** football-data.org is match/aggregate level: goals, cards
and substitutions with minutes, but **no shots, passes, xG or coordinates**. A
live twin fed from it has a real score, goal/card timeline, momentum, regime and
predictions — but not the shot-level texture of a StatsBomb replay. Event-grade
live data only exists behind paid providers (Opta, StatsBomb live, Sportmonks).

## Using it

The connector is `fie.sources.footballdata.FootballDataSource`, wired to Live
Mode through `backend/app/livefeed.py` and the `POST /live/{id}/footballdata`
endpoint.

```bash
# 1. get a free key at https://www.football-data.org/client/register
export FOOTBALL_DATA_API_KEY="your-free-key"     # unlocks goal/card events

# 2. with the backend running, feed a live match (fd_id from /v4/matches):
curl -X POST "http://localhost:8000/live/mygame/footballdata?fd_id=537113"
#    -> starts/updates a live session; returns the corrected twin state.
#    Poll on an interval; it is idempotent (only new events are fed).
```

Without a key the endpoint still resolves the fixture and score from the keyless
scoreboard, but no events flow (the provider withholds the detail arrays) — so a
key is required for a meaningful live feed.

## Reproduce the research

The connector's keyless reachability is covered by a network-gated test (skipped
in CI):

```bash
FUTK_LIVE_TESTS=1 pytest tests/test_footballdata_live.py
```

The v4 → engine mapping is covered offline against the real provider schema in
`tests/test_footballdata.py` (no network, no key).
