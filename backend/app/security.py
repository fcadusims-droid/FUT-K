"""Security (product level 17): API keys + rate limiting, env-configured.

- **API keys**: set ``FUTK_API_KEYS=key1,key2`` to require an ``X-API-Key``
  header on every endpoint except ``/health``, ``/docs`` and the OpenAPI
  schema. Unset (the default) the API stays open — right for local use and
  the bundled frontend.
- **Rate limiting**: a per-caller token bucket (key if present, else client
  IP). ``FUTK_RATE_LIMIT`` requests per ``FUTK_RATE_WINDOW`` seconds
  (default 120 / 60s). Returns 429 with a Retry-After header.
- **Proxy awareness**: set ``FUTK_TRUST_PROXY=1`` when a reverse proxy (the
  bundled nginx frontend) sits in front, so the caller is identified by the
  first ``X-Forwarded-For`` hop instead of the proxy's own IP — otherwise
  every browser behind the proxy shares one bucket. Only enable it when the
  proxy is the sole way in: a caller that can reach the API directly can
  spoof the header (which only lets it pick its *own* bucket).

In-process by design — one worker, no external store. If FUT-K is ever
deployed multi-worker, move the bucket to a shared store; the interface here
stays the same.
"""

from __future__ import annotations

import os
import secrets
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

EXEMPT = ("/health", "/docs", "/openapi.json", "/redoc")


def _api_keys() -> set:
    raw = os.environ.get("FUTK_API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def _trust_proxy() -> bool:
    return os.environ.get("FUTK_TRUST_PROXY", "").lower() in ("1", "true", "yes")


def _caller_ip(request) -> str:
    """The rate-limit identity: the real client, even behind the bundled nginx."""
    if _trust_proxy():
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._lock = threading.Lock()
        self._hits: dict = {}
        self._last_sweep = time.time()

    def _sweep(self, now: float) -> None:
        """Drop callers with no hit inside the window, so the dict stays
        bounded on a public deployment (distinct IPs would otherwise
        accumulate forever). Runs at most once per window."""
        if now - self._last_sweep < self.window:
            return
        cutoff = now - self.window
        self._hits = {
            caller: kept
            for caller, ts in self._hits.items()
            if (kept := [t for t in ts if t > cutoff])
        }
        self._last_sweep = now

    def allow(self, caller: str) -> tuple:
        now = time.time()
        with self._lock:
            self._sweep(now)
            hits = [t for t in self._hits.get(caller, []) if now - t < self.window]
            if len(hits) >= self.limit:
                retry = self.window - (now - hits[0])
                self._hits[caller] = hits
                return False, max(1, int(retry))
            hits.append(now)
            self._hits[caller] = hits
            return True, 0


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.limiter = RateLimiter(
            limit=int(os.environ.get("FUTK_RATE_LIMIT", "120")),
            window=float(os.environ.get("FUTK_RATE_WINDOW", "60")),
        )

    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in EXEMPT:
            return await call_next(request)

        keys = _api_keys()
        caller = _caller_ip(request)
        if keys:
            provided = request.headers.get("X-API-Key", "")
            # compare_digest against every key: constant-time per comparison,
            # so the match cannot be timed out of the check.
            if not any(secrets.compare_digest(provided, k) for k in keys):
                return JSONResponse({"detail": "invalid or missing API key"},
                                    status_code=401)
            caller = provided

        ok, retry = self.limiter.allow(caller)
        if not ok:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429,
                                headers={"Retry-After": str(retry)})

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response
