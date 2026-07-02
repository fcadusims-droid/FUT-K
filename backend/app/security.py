"""Security (product level 17): API keys + rate limiting, env-configured.

- **API keys**: set ``FUTK_API_KEYS=key1,key2`` to require an ``X-API-Key``
  header on every endpoint except ``/health``, ``/docs`` and the OpenAPI
  schema. Unset (the default) the API stays open — right for local use and
  the bundled frontend.
- **Rate limiting**: a per-caller token bucket (key if present, else client
  IP). ``FUTK_RATE_LIMIT`` requests per ``FUTK_RATE_WINDOW`` seconds
  (default 120 / 60s). Returns 429 with a Retry-After header.

In-process by design — one worker, no external store. If FUT-K is ever
deployed multi-worker, move the bucket to a shared store; the interface here
stays the same.
"""

from __future__ import annotations

import os
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

EXEMPT = ("/health", "/docs", "/openapi.json", "/redoc")


def _api_keys() -> set:
    raw = os.environ.get("FUTK_API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._lock = threading.Lock()
        self._hits: dict = {}

    def allow(self, caller: str) -> tuple:
        now = time.time()
        with self._lock:
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
        caller = request.client.host if request.client else "unknown"
        if keys:
            provided = request.headers.get("X-API-Key", "")
            if provided not in keys:
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
