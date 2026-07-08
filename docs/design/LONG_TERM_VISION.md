# FUT-K long-term vision

> The horizon beyond the current product: FUT-K as an **intelligence
> infrastructure for football** — institutional-grade, universal, federated and
> able to run anywhere, online or off. This document records that vision, maps it
> honestly against what the codebase is **today**, and names the concrete path.

It obeys the project's founding invariants — **deterministic & reproducible**,
**honest** (uncertainty shown, negatives kept, provenance everywhere, nothing
fabricated), and the two enforced architecture rules
([`ARCHITECTURE.md`](../ARCHITECTURE.md)): dependencies point down, and no module
consumes external data directly (everything canonical, via the Dataset Fusion).

Status legend: ✅ done · 🟡 partial / foundation present · ⬜ planned · 🔒 needs a
non-code input (data source, institutional agreement, governance).

## Why the foundation already fits

None of this is a rewrite. The last several PRs hardened exactly the substrate
these visions need:

- a **pure, standard-library, deterministic engine** (`src/fie`) that runs
  offline anywhere — the edge/independence prerequisite;
- the **canonical Dataset Fusion** (Raw → Normalized → Canonical) with the
  *no-direct-external-data* rule enforced by a test — so official sources plug in
  at the boundary and consumers never depend on a provider;
- a **provenance / temporal / isolation contract** and an append-only knowledge
  store — the right substrate for federated, traceable, versioned knowledge;
- a **promotion-gated learning loop** (`recalibrate.py`, `model_versions`) — the
  right substrate for sharing and validating models across a network.

What is missing is almost entirely the **outer layers**: real-time/streaming
infrastructure, the computer-vision subsystem, multi-tenancy, distributed /
federated infrastructure, packaging — plus the non-code parts.

## The four visions vs. today

### 1. Institutional integration (official APIs, DBs, tracking, sensors, real-time)
- **Today (🟡):** the modular `Source` ABC + canonical pipeline mean a new
  official/tracking/sensor feed plugs in **at the ingestion boundary without
  touching any consumer**. Connectors exist for StatsBomb, football-data.org,
  Wikidata, football-data.co.uk, openfootball.
- **Gap:** connectors for official/tracking/sensor feeds; real-time **streaming
  ingestion at scale** (Live Mode is now DB-backed and stateless — see below —
  but there is no stream/queue); institutional authN/Z.
- **Non-code (🔒):** data-access agreements with federations/leagues.

### 2. Real-time computer vision (video → positions, pressing, lines)
- **Today (🟡):** the **Vision Engine** (`fie.vision`) is a continuous
  self-correcting state estimator whose kinematic model is *already architected
  for a dense 22-player tracking feed*, and the canonical `Event` already carries
  pitch coordinates.
- **Gap:** the entire CV stack — video ingestion, player detection/tracking,
  homography to pitch coordinates, event detection — as the **producer** behind
  the tracking connector (`fie.sources.tracking`, now shipped) that already feeds
  the Vision Engine. Large ML/GPU subsystem; the architecture and the consumer are
  ready, only the CV producer is missing.

### 3. Continuous learning
- **Today (🟡):** `recalibrate.py` + the **held-out promotion gate** (promote only
  if held-out log-loss doesn't degrade) + `model_versions`; player profiles
  rebuilt from per-season rows; the temporal/provenance contract preserves history.
- **Gap:** automated orchestration (refit triggered on new data); incremental
  learning at scale. *(The **Knowledge Graph** over the canonical store now
  exists — `fie.graph` / `GET /knowledge/graph`.)*

### 4. Global scalability (thousands of matches, near-real-time world state)
- **Today (🟡):** the pure/deterministic engine scales horizontally in principle;
  Postgres; Docker. **Live Mode sessions are now stateless (DB-backed)** — the
  first concrete scale blocker, removed (`live_sessions` / `live_observations`;
  any worker rebuilds any session from the store).
- **Gap:** a stream/queue for high-throughput ingestion; sharding; a
  cross-request cache; horizontal worker deployment; observability at scale.

### 5. Universal platform (every size; democratization; interoperability)
- **Today (🟡, strong):** zero-setup **SQLite** fallback, stdlib engine, Docker,
  **bring-your-own-data** (CSV ingestion + `recalibrate` behind the same gate).
  A small academy can already run FUT-K locally.
- **Gap:** multi-tenant / accounts / per-org isolation; i18n (PT-BR planned);
  packaging for non-technical users.

### 6. Global Federation FUT-K (shared infra & intelligence, distributed nodes)
- **Today (⬜ for the federation layer; 🟡 substrate):** none of the federation
  exists, **but** the canonical provenance/isolation/versioning contract and
  `model_versions` + promotion gate are the right substrate for sharing knowledge
  and models with traceability and quality gates.
- **Gap:** a node-to-node **sync protocol**; a "federation node" concept; model /
  knowledge distribution; inter-node identity & trust; data-sovereignty controls.
- **Non-code (🔒):** federation governance, access policies, membership.

### 7. Local infrastructure / independence / edge / offline
- **Today (🟡, strongest):** the engine is **stdlib-only and fully offline**; the
  backend runs on SQLite with no external dependency; data is cached on disk and
  then works offline; determinism makes it reproducible offline; the
  no-direct-external rule means **consumers never need the internet**.
- **Gap:** a pre-configured **appliance** distribution ("install, runs on power +
  LAN only"); a **sync client** to the Federation (depends on §6); per-org
  **data-sovereignty** policy controls; offline model distribution.

## The concrete path (readiness items, in order)

Buildable now, on the existing core, without fabricating data:

1. **Externalize Live Mode sessions** — ✅ **done.** State moved to
   `live_sessions` / `live_observations`; sessions are stateless and portable
   across workers (the §4 blocker). The in-memory `LiveMatch` remains the pure
   compute object the store rebuilds; "streamed == batch" preserved.
2. **Knowledge Graph over the canonical store** — ✅ **done.** `fie.graph`
   derives a queryable graph (player ↔ team ↔ match ↔ competition) from each
   record's context, every edge carrying temporal validity and provenance; served
   at `GET /knowledge/graph` (whole graph, a node's neighbourhood with `as_of`, or
   a type's nodes). Feeds §1, §3, §6.
3. **Institutional connector SDK** — ✅ **done.** The connector guide
   ([`CONNECTORS.md`](./CONNECTORS.md)) formalizes the two connector shapes (the
   on-ball `Source` ABC and a positional/tracking connector) + how they reach the
   canonical layer, and ships a reference **tracking connector**
   (`fie.sources.tracking`, open 7-field CSV/JSON) that feeds the Vision Engine and
   the canonical pipeline — proving §1 interoperability and readying §2 (CV: the
   consumer exists, only the producer is missing).
4. **Offline appliance packaging** — ⬜ a self-contained image/compose that runs
   on power + LAN only (§7), with a data-sovereignty manifest (which layers stay
   local vs. syncable).

Beyond these lie the large programs (the CV subsystem, streaming at scale,
multi-tenancy, the Federation sync protocol and its governance), each of which
enters through the same canonical front door when its inputs — data, hardware, or
institutional agreements — exist. Nothing is built ahead of the evidence for it.
