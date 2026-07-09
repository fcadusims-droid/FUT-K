# Deploying FUT-K (product level 16)

## One-command service

```bash
docker compose up --build          # postgres + backend (:8000) + frontend (:8080)
```

First run: ingest data inside the backend container —

```bash
docker compose exec backend python scripts/ingest.py --pairs "43/3,16/*,11/27"
```

## The pieces

| Concern | How it's covered |
|---|---|
| Images | `backend/Dockerfile` (engine + API), `frontend/Dockerfile` (Vite build → nginx) |
| CI/CD | `.github/workflows/tests.yml` (engine) + `backend-tests.yml` (API, 3.11/3.12) + `app.yml` (frontend build, Docker builds) on every push/PR |
| Monitoring | `GET /metrics` (JSON) and `GET /metrics/prometheus` — per-route requests, errors, p95 latency, uptime |
| Logs | uvicorn access + app logs to stdout; collect with the platform (Docker logs, journald, or a shipper) |
| Rollback | images are immutable — tag releases (`futk-backend:vX.Y`) and roll back by redeploying the previous tag; the DB schema is additive so old code runs against new schema |
| Health | `GET /health` for liveness; compose healthcheck gates Postgres |
| Secrets | env only: `DATABASE_URL`, `FUTK_API_KEYS`, `FUTK_DB_PASSWORD` — never in the image |
| Proxy | `FUTK_TRUST_PROXY=1` (compose default) makes rate limiting identify callers by the first `X-Forwarded-For` hop — required behind the bundled nginx, where every browser would otherwise share the proxy's IP bucket. Enable it only when the proxy is the sole way in: a caller with direct API access can spoof the header (which only picks its own bucket). |

## Data & model operations

- Refresh (incremental ingest + quality audit): `python scripts/refresh.py`
  — run daily via cron/systemd timer; every run is recorded in
  `ingestion_runs` (level 18).
- Recalibration (the learning loop): `python scripts/recalibrate.py`
  — refits on the latest data, promotes a new model version **only if it does
  not degrade** held-out metrics; history at `GET /model/versions` (level 19).

## Scaling note

Rate limiting and metrics are in-process (single worker). For multi-worker
deployments put them behind a shared store (Redis) — the middleware interfaces
are already isolated for that swap.
