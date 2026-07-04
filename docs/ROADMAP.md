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
by construction) and ~25 API endpoints already expose momentum, regimes,
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

## Phase 2 — Live data + more leagues · ⬜ (needs external inputs)

Live Mode and the fusion layer are built and proven offline; what's missing is a
real feed. **Requires a provider API key / license** — cannot be completed
without it, and no fake feed will be shipped.

| Item | Effort | Status | Notes |
|---|---|---|---|
| A live `Source` (subclass `fie/sources/base.py::Source`, injectable loaders like `StatsBombSource`) plugged into the event bus | L | ⬜ | needs credentials (e.g. football-data.org from the data guide) |
| Ingest more Big-5 seasons via the pipeline (`refresh_pair` → `recalibrate` with the held-out promotion gate) | M | ⬜ | promote only if held-out log loss doesn't degrade |
| Live-stream validation (validation §7) | M | ⬜ | prove streamed state == batch panel on a real feed |

**First concrete step (no core edits):** implement `Source.matches()` /
`Source.stream()` for the chosen provider with an injectable HTTP loader so it is
unit-testable offline against a recorded fixture, exactly as `StatsBombSource`
already is; wire it to `backend/app/live.py`.

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
