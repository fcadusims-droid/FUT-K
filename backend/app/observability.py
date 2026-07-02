"""Observability (product level 15): measure everything, in-process.

A dependency-free metrics registry + ASGI middleware: per-route request
counts, error counts, latency (mean and p95 from a bounded reservoir), and
process uptime — exposed at ``GET /metrics`` as JSON and at
``GET /metrics/prometheus`` in Prometheus text format for scrapers.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware

RESERVOIR = 200  # latencies kept per route (bounded memory)


class Metrics:
    def __init__(self):
        self.started = time.time()
        self._lock = threading.Lock()
        self.requests: dict = defaultdict(int)
        self.errors: dict = defaultdict(int)
        self.latencies: dict = defaultdict(list)

    def observe(self, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[route] += 1
            if status >= 500:
                self.errors[route] += 1
            lat = self.latencies[route]
            lat.append(seconds)
            if len(lat) > RESERVOIR:
                del lat[: len(lat) - RESERVOIR]

    def snapshot(self) -> dict:
        with self._lock:
            routes = {}
            for route, n in sorted(self.requests.items()):
                lat = sorted(self.latencies[route])
                mean = sum(lat) / len(lat) if lat else 0.0
                p95 = lat[int(0.95 * (len(lat) - 1))] if lat else 0.0
                routes[route] = {
                    "requests": n,
                    "errors": self.errors[route],
                    "latency_mean_ms": round(mean * 1000, 2),
                    "latency_p95_ms": round(p95 * 1000, 2),
                }
            return {
                "uptime_seconds": round(time.time() - self.started, 1),
                "total_requests": sum(self.requests.values()),
                "total_errors": sum(self.errors.values()),
                "routes": routes,
            }

    def prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            "# TYPE futk_requests_total counter",
            "# TYPE futk_errors_total counter",
            "# TYPE futk_latency_p95_ms gauge",
        ]
        for route, s in snap["routes"].items():
            label = f'{{route="{route}"}}'
            lines += [
                f"futk_requests_total{label} {s['requests']}",
                f"futk_errors_total{label} {s['errors']}",
                f"futk_latency_p95_ms{label} {s['latency_p95_ms']}",
            ]
        lines.append(f"futk_uptime_seconds {snap['uptime_seconds']}")
        return "\n".join(lines) + "\n"


metrics = Metrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Times every request; groups by route template (not raw path) so
    /matches/7525 and /matches/7584 share one series."""

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            metrics.observe(path, status, time.perf_counter() - start)
