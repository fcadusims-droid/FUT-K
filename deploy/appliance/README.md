# FUT-K Offline Appliance

Run FUT-K **on power + LAN only** — no internet at runtime. This is the
independence/edge vision made concrete
([`../../docs/design/LONG_TERM_VISION.md`](../../docs/design/LONG_TERM_VISION.md) §7):
the engine is standard-library and deterministic, the backend runs on a local
database, and once the images are built (which needs the internet once) the whole
stack serves entirely offline.

## What makes it offline

- **`FUTK_OFFLINE=1`** — the backend refuses any endpoint that reaches an external
  provider (the football-data.org live feed returns `503`). Everything else — the
  panel, simulation, scouting, tactics, the twin, the Knowledge Graph — is a pure
  function of local data and needs no network.
- **Local raw cache** — the passing network and twin stream build from the local
  `.sb_cache`; the serving path never downloads (the data-boundary rule).
- **Local database** — Postgres in the compose, or SQLite for a single-box install
  (omit `DATABASE_URL`).

## Run it

```bash
# build once (needs the internet for base images + deps), then run offline:
docker compose -f deploy/appliance/docker-compose.offline.yml up --build
# open http://<appliance-host>:8080 on the local network
```

Ingest on the appliance from local or cached data (the ingestion scripts under
`backend/scripts/`), or bring your own via the open CSV/JSON formats
(`docs/CUSTOM_DATA.md`, the tracking connector `docs/design/CONNECTORS.md`).

## Data sovereignty

Each institution controls its own data. **Nothing leaves by default** — the
sovereignty policy denies all sync until you allow specific knowledge. See
[`sovereignty.example.toml`](./sovereignty.example.toml); supply it as the
`FUTK_SOVEREIGNTY` env var (JSON). Then:

- `GET /sovereignty` shows the active policy;
- `GET /knowledge/sync-view` returns **only** what the policy allows to leave —
  all a Federation sync client could ever pull. Empty by default.

## Scale, one architecture

The same components run at every size (`§ Modular scalability`): a single compact
server for a small academy, a small cluster for a university, a datacenter for a
national federation. Live Mode is stateless (DB-backed), so add workers behind the
API and any of them serves any match.
