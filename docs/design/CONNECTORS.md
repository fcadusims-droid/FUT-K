# Connector SDK — plug any source into FUT-K

> How an institution feeds its data into FUT-K. The architecture rule holds
> everywhere ([`ARCHITECTURE.md`](../ARCHITECTURE.md)): a connector is the **only**
> place a provider is read; it normalizes the provider's data at the ingestion
> boundary, and everything downstream consumes the **canonical** FUT-K dataset —
> never the source. Swap StatsBomb for Opta, add a tracking feed, ingest a CSV:
> simulation, scouting, tactics and the twin do not change.

A connector's whole job is: **provider bytes → normalized records → the canonical
pipeline.** It is pure (no globals, deterministic), lives under `fie/sources/`
(or the backend ingestion allowlist), and invents nothing the provider did not
report.

## Two connector shapes

FUT-K has two data modalities, each with a tiny surface:

### 1. On-ball events — the `Source` ABC

For providers of discrete match events (passes, shots, cards…). Implement
[`fie.sources.base.Source`](../../src/fie/sources/base.py):

```python
class Source(ABC):
    name: str
    base_trust: float          # prior reliability, 0..1 (feeds the fusion vote)

    def stream(self, match_id):
        """Yield normalized fie.events.Event objects for match_id."""
```

Each `Event` is the normalized shape (`match_id, minute, team, type, player_id?,
target_id?, x?, y?, xg?`). Unknown event types simply carry zero offensive
weight — the engine degrades honestly. Reference: `fie.sources.statsbomb`,
`fie.sources.footballdata`.

### 2. Positional / tracking — a frame connector

For dense positional feeds (optical tracking, computer vision, sensors). A
tracking connector emits **frames** — a player's `(t, x, y)` sampled over time —
which flow straight into the Vision Engine the Digital Twin already runs.
Reference: [`fie.sources.tracking`](../../src/fie/sources/tracking.py), which
parses an **open 7-field CSV/JSON** so it needs no proprietary SDK:

```csv
t,player_id,team,x,y,player
0.0,7,HOME,52.4,48.1,A. Winger
```

```python
from fie.sources.tracking import TrackingConnector
frames = TrackingConnector().frames(open("feed.csv").read())     # normalized
items  = to_vision_items(frames)                                 # → fie.vision
records = to_canonical_records(frames, match_id="m1", source="optical-x")
```

A real Opta / Second Spectrum / CV producer implements the same small surface;
the *consumer* (the Vision Engine's continuous state estimator) is already built
and validated, which is why real-time CV needs only this producer.

## Reaching the canonical layer

However a connector normalizes, the ingestion step lifts the result into the
**canonical** dataset ([`fie.canonical`](../../src/fie/canonical.py)):

- **Raw** — keep the provider payload intact (`raw_record`, never modified).
- **Normalized** — unified field/entity names (`normalize_entity` /
  `normalize_person`).
- **Canonical** — FUT-K's own global ids via identity resolution
  (`canonical_player_id` / `canonical_team_id` / `canonical_match_id`), so the
  same entity across providers is one node — with provenance kept for traceability.

From there it enters the knowledge store under the full contract (context,
provenance, temporal validity, isolation), joins the Knowledge Graph
(`fie.graph`), and is available to every AI module. Cross-provider facts are
reconciled by the fusion layer (`fie.fusion`) with recorded dissent — differences
are surfaced, never silently overwritten.

## Rules for a connector

1. **Only under the ingestion boundary.** Connectors live in `fie/sources/` or
   the backend ingestion allowlist; no serving module imports them
   (`tests/test_data_boundary.py` enforces it).
2. **Pure & deterministic.** Same bytes in, same records out. Parsing only — the
   ingestion script (Application) supplies the provider's bytes.
3. **Normalize, don't invent.** Map exactly what the provider reports; skip a
   malformed record rather than guessing it; state coarseness rather than papering
   over it.
4. **Declare `base_trust`.** A prior the fusion vote uses; the loop then *measures*
   each source's real reliability (`fie.fusion.priors_from_agreement`).
