# Scout AI — intelligent talent discovery

> Vision: find players whose *development pattern* — not just current stats —
> resembles the trajectories of players who reached the top.

This document maps that vision onto what is **shipped today**, what each piece
honestly is, and what the next stages need. FUT-K's rules apply here with full
force: every number traces to real data, unknown facts stay unknown, and a
descriptive heuristic is never dressed up as a trained predictor.

## What ships today

| Vision component | Shipped as | Honest status |
|---|---|---|
| **Player Evolution Timeline** | `player_season_profiles` — full behavioral counters per (player, competition, season); `GET /players/{id}/evolution` returns the season-by-season timeline ordered by real match dates | ✅ the storage + API primitive; grows a real trajectory as more seasons are ingested |
| **Development similarity** ("similar to X") | `GET /players/{id}/similar` — cosine similarity over normalized behavioral profile vectors (`fie.scouting`) | ✅ shipped, but it is **style similarity of observed profiles**, not trajectory similarity — that needs multi-season coverage per player (the timeline above is how it accrues) |
| **Potential Score** | the **scout index** (`GET /scout/rankings`) — cohort percentiles of observed rates (attack, creation, progression, security) × evidence-volume weight × age factor when a verified birth date exists | ✅ shipped as a **transparent, documented, descriptive index**. It is *not* a trained potential model — see "The honest boundary" |
| **Discovery radar (filters)** | `/scout/rankings?position=&max_age=&min_confidence=&competition=&season=` + the **Scout tab** in the app | ✅ age filters only include players with a *verified* birth date — never a guessed age |
| **Physical/bio data** | `player_bios` fused from **Wikidata** (CC0): birth date, height, position, citizenship — each row carries the source, the matched entity QID and the fetch date (`backend/scripts/enrich_bios.py`) | ✅ occupation-filtered entity matching (a same-named non-footballer never matches); no confident match → **no row** |
| **Fusion expanded / more data** | 80 real competition/season pairs are available in StatsBomb open data (Copa América 2024, MLS 2023, Africa Cup 2023, Serie A, Premier League, Ligue 1 ×3, Argentina, Copa del Rey, Europa League, …) — ingest with `backend/scripts/ingest.py` | ✅ measured live; the learning loop's promotion gate calibrates on each new competition (verified: a Copa América 2024 refit **promoted** on held-out log loss 0.491 vs 0.511) |
| **Youth (U15/U17/U20) history** | the schema treats youth competitions as ordinary competitions — StatsBomb open data contains **FIFA U20 World Cup 1979** (ingested and working; it is how Maradona's real U20 profile enters the similarity space) | 🟡 the *pipeline* is proven on real youth data, but free longitudinal youth coverage does not exist — see below |

## Verified end-to-end (real data, reproducible)

The full loop was exercised on live sources:

1. **Ingest** Copa América 2024 (32 matches) + U20 World Cup 1979 → 339 + 26
   season profiles. Re-runs **skip everything already ingested** and raw
   downloads are cached (`.sb_cache/`) — the same byte is never fetched twice.
2. **Quality gate caught a real extraction bug**: penalty-shootout kicks
   (period 5) were being counted as goals ("goal events 5-6 != final 2-2" on
   four CA-2024 knockouts). Fixed in the connector; the same matches now pass
   clean. Shootout kicks are not in-play events.
3. **Enrich** bios from Wikidata (rate-limit-respecting, disk-cached):
   real birth dates/heights landed for Romero, Lisandro Martínez, Valverde,
   James Rodríguez, De Paul, Marquinhos, ….
4. **Calibrate**: `recalibrate.py --from-db --competition 223` → the refit
   **promoted** by the held-out gate (CA 2024 is low-scoring; the model
   learned that honestly).
5. **Radar**: Messi tops the CA-2024 cohort; his most similar observed
   profiles are Di María (98%) and — from the real 1979 U20 data — **Diego
   Maradona (97%)**. Cross-era style similarity from real events.

```bash
cd backend
python scripts/ingest.py --pairs "223/282,1470/274"        # real matches (cached)
python scripts/enrich_bios.py --min-actions 250 --limit 25 # real bios (Wikidata)
python scripts/recalibrate.py --from-db --competition 223  # gate-kept calibration
# then: GET /scout/rankings · /players/{id}/similar · /players/{id}/evolution
```

## The honest boundary (read this before selling it)

* **The scout index is descriptive.** It says *"this player's observed rates
  sit high in this real cohort, with this much evidence, at this (verified)
  age"*. It does **not** estimate the probability of reaching elite level —
  training that model requires labeled development trajectories
  (youth-season → adult-outcome pairs) which free data does not provide today.
  Every component of the index is exposed in the payload so nobody can
  mistake it for an oracle.
* **Similarity is style, not destiny.** 97% similar to Maradona means the
  observed behavioral profile (pass/dribble/shot/turnover mix) is close —
  on the data we have — not that a comparable career follows.
* **Free youth data is nearly nonexistent.** StatsBomb open data has exactly
  one youth tournament (U20 WC **1979**). Building the "U15→U17→U20→pro"
  learning corpus the vision describes requires licensed providers (Wyscout/
  StatsBomb paid, federation feeds). The schema and pipeline are ready for it:
  a youth season is just another `(competition, season)` row.
* **Wikidata matching is by name + occupation.** Homonym footballers could in
  principle collide; every row carries its QID so any match can be audited,
  and unmatched players simply have no bio.

## What the next stage needs (external inputs)

1. **Licensed youth event data** → real trajectories → then (and only then) a
   trained development model, promoted through the same held-out gate the
   goal model uses.
2. **More seasons per player** from the free pool (ingest more of the 80
   available pairs) → trajectory similarity becomes meaningful over the
   evolution timeline that is already recorded.
3. **Market/contract data** (the vision's "undervalued" alerts) → no free,
   licensed source; documented as out of scope until one exists.
