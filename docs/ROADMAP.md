# FUT-K roadmap

> North star: the **Digital Football Twin** ([`VISION.md`](./VISION.md)).
> Product identity: the match intelligence terminal ([`product/PRODUCT.md`](./product/PRODUCT.md)).

This is the phased plan to develop FUT-K "more and better". Every item respects
the project's founding invariants — **deterministic & reproducible**, **honest**
(uncertainty shown, negatives kept, provenance everywhere, nothing fabricated),
and the **layered architecture** ([`ARCHITECTURE.md`](./ARCHITECTURE.md), one
dependency rule enforced by a test; extend via plugins, not core edits).

Status legend: ✅ shipped · 🟡 in progress / partial · ⬜ planned.
Effort: S (hours) · M (days) · L (weeks+).

## Diagnosis

The engine is far ahead of the app. The validated core (`src/fie`, leakage-safe
by construction) and ~38 API endpoints already expose momentum, regimes,
calibrated predictions, fusion, future simulation, the strategic assistant, the
vision engine, live mode and player DNA. The biggest lever is **surfacing** that
capability in the product, then broadening data coverage and going live.

---

## Phase 0 — Hygiene & quick wins · ✅ done

| Item | Effort | Status |
|---|---|---|
| Fix `TimelineChart` exhaustive-deps lint warnings | S | ✅ |
| Silence starlette's third-party TestClient deprecation in backend pytest | S | ✅ |
| Reconcile stale test counts across docs (engine 236, API 72, 308 total) | S | ✅ |
| Read active model params once per request (N+1 fix) | S | ✅ (earlier) |
| Evidence-based confidence + provenance on player DNA | M | ✅ (earlier) |

## Phase 1 — Close the product↔engine gap in the UI · 🟡 (flagship shipped)

The highest-ROI phase: make the engine's capability discoverable.

| Item | Effort | Status |
|---|---|---|
| Dependency-free hash router — deep-linkable, shareable views (`#/match/:id`, `#/players`, `#/player/:id`) | S | ✅ |
| **Player DNA directory** (`#/players`): archetype filter + min-confidence slider; rows show confidence + provenance | M | ✅ |
| Top-level **Players** tab; title links home | S | ✅ |
| Promote Simulate / Strategy / Vision / Live from cards-inside-replay to first-class, described surfaces | M | ⬜ |
| i18n + PT-BR (start with the humanized panel & Match Story) | M | ⬜ |
| Visual polish pass (shared chart system, dark/light parity, mobile layout) | M | ⬜ |

**Done criterion:** a new user discovers Simulate, Strategy, Vision and Player
DNA without instruction; links are shareable. (Player DNA + deep-linking: done.)

## Phase 2 — Live data + more leagues · 🟡 (free live source shipped)

Live Mode and the fusion layer were built and proven offline; a **free live
source is now wired in**. Research + decision: [`DATA_SOURCES.md`](./DATA_SOURCES.md).

| Item | Effort | Status | Notes |
|---|---|---|---|
| A live `Source` for **football-data.org** (`fie.sources.footballdata`) — v4 → normalized events, injectable loader, keyless + API-key tiers | L | ✅ | the only free live-capable API in the guide; verified against the real endpoint |
| Wire it into Live Mode: `backend/app/livefeed.py` + `POST /live/{id}/footballdata` (idempotent polling) | M | ✅ | feeds only new events into the event-bus session |
| **Live insights** — turn the observation stream into semantic beats (goal / regime shift / momentum swing) in real time, reusing the Match-Story kernel (`story.transition_beat`); surfaced in the snapshot + `LivePanel` | M | ✅ | the live twin reads the feed as match *understanding*, not a raw event log |
| Free API key to unlock goal/card **events** (`FOOTBALL_DATA_API_KEY`) | S | ⬜ | user provides a free key — the one remaining external input |
| Ingest more Big-5 seasons via the pipeline (`refresh_pair` → `recalibrate` with the held-out promotion gate) | M | ⬜ | promote only if held-out log loss doesn't degrade |
| Live-stream validation (validation §7) | M | ⬜ | prove streamed state == batch panel on a real feed during a live match |

**Honest limitation (documented, not hidden):** football-data.org is
match/aggregate level (goals, cards, subs with minutes) — no shots/xG/coordinates.
The live twin gets a real score, goal/card timeline and everything derived from
them; event-grade live texture needs a paid provider.

## Phase 2.5 — Scout AI (talent discovery) · 🟡 (foundations shipped)

Vision → shipped mapping, honest boundaries and the verified real-data run:
[`SCOUT.md`](./SCOUT.md).

| Item | Effort | Status | Notes |
|---|---|---|---|
| Player Evolution Timeline (`player_season_profiles` + `/players/{id}/evolution`) | M | ✅ | full counters per (player, competition, season); global profile = exact sum (fixes last-ingest-wins) |
| Behavioral similarity (`/players/{id}/similar`) + Scout index + radar (`/scout/rankings`, Scout tab) | M | ✅ | descriptive & transparent — NOT a trained potential model |
| Wikidata bio fusion (birth date/height/position/citizenship, QID provenance, cached) | M | ✅ | `enrich_bios.py`; unmatched players stay unknown |
| Calibration on new competitions via the promotion gate | M | ✅ | verified: Copa América 2024 refit promoted (held-out LL 0.491 vs 0.511) |
| Trained development model (trajectory learning) | L | ⬜ | needs licensed longitudinal youth data (only free youth tournament: U20 WC 1979) |

## Phase 3 — Richer in-play intelligence & tracking-ready · ⬜ (research + data)

| Item | Effort | Status | Notes |
|---|---|---|---|
| Richer in-play features | L | ⬜ | open research question (validation §7); calibration is the judge, negatives kept |
| Tracking-data ingestion path | L | ⬜ | needs a tracking feed; the Vision Engine kinematic model is already architected for it (full 22-player continuity) |
| ROI / market analysis | M | ⬜ | honestly labelled — the engine sits below the closing line by design |

## Phase 4 — Platform & product · ⬜ (product decisions)

| Item | Effort | Status |
|---|---|---|
| Accounts / multi-user, favorites, saved workspaces | L | ⬜ |
| Mobile (PWA first, then native) | L | ⬜ |
| Evolved observability (tracing, dashboards, alerts on `/metrics`) | M | ⬜ |
| Publish SDKs to PyPI / npm | S | ⬜ |

## Phase 5 — Intelligence infrastructure (long-term vision) · 🟡 (foundation)

The horizon: FUT-K as institutional-grade, universal, federated, run-anywhere
infrastructure. Full vision and the honest state-vs-gap map:
[`design/LONG_TERM_VISION.md`](./design/LONG_TERM_VISION.md). Readiness items,
buildable now on the existing core:

| Item | Effort | Status | Notes |
|---|---|---|---|
| **Externalize Live Mode sessions** (DB-backed, stateless) | M | ✅ | `live_sessions`/`live_observations`; any worker rebuilds any session — the horizontal-scale/edge blocker, removed |
| Knowledge Graph over the canonical store | L | ⬜ | queryable entity/relation graph over time; feeds institutional integration, continuous learning, federation |
| Institutional connector SDK + reference tracking connector | L | ⬜ | formalize `Source` ABC + canonical pipeline; opens the door to real-time CV |
| Offline **appliance** packaging + data-sovereignty manifest | M | ⬜ | "install, runs on power + LAN only" (edge/independence) |
| Real-time computer-vision ingestion | L | 🔒 | Vision Engine is architected for a dense tracking feed; the CV producer needs ML/GPU + data |
| Federation sync protocol + governance | L | 🔒 | canonical provenance/versioning is the substrate; needs distributed-systems build + governance |

---

## Cross-cutting — performance & scale

| Item | Effort | Status | Notes |
|---|---|---|---|
| Memoize `/similar` match vectors by events digest | M | ✅ | correct invalidation via `events_hash`; no schema change |
| Panel/timeline cross-request cache | M | ⬜ (deferred) | **intentionally deferred**: correct invalidation adds real risk, and the architecture doc's anti-complexity stance ("Core functions *are* the feature definitions, computed on demand") argues against it until a measured need appears. Within a single request the panel is already computed once per minute; the earlier N+1 fix removed the redundant per-minute param reads. |
| Indexing & pagination on `/matches`, `/players/profiles`, `/search` | M | ⬜ | |

## Recommended sequence

```
Phase 0 ✅  →  finish Phase 1 (surface modes, i18n, polish)  →  perf backlog
                                            ↘  Phase 2 (live + leagues)
                                                      ↘ Phase 3 (research) ↘ Phase 4 (platform)
```

Start by finishing Phase 1 — the engine already delivers; the app needs to
*show* it. Everything below Phase 1 either needs external inputs (a live
provider key, tracking data) or product decisions (accounts, mobile), documented
above so they can be picked up the moment those inputs exist.

## Success metrics

- **Product:** share of engine capabilities reachable in ≤ 2 clicks; modes a new user finds unaided.
- **Quality:** CI green; architecture-test intact; the 73:15 leakage gate never regresses.
- **Data:** leagues/seasons with a *promoted* refit; profiles with `confidence ≥ 0.5`.
- **Performance:** p95 latency of `/timeline` and `/similar` after the caching work.
