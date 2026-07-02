"""Levels 15 & 17: metrics, API keys, rate limiting."""

from __future__ import annotations


from app.security import RateLimiter


def test_metrics_counts_requests(client):
    client.get("/matches")
    client.get("/matches")
    snap = client.get("/metrics").json()
    assert snap["total_requests"] >= 2
    assert snap["routes"]["/matches"]["requests"] >= 2
    assert snap["routes"]["/matches"]["errors"] == 0
    assert snap["routes"]["/matches"]["latency_p95_ms"] >= 0
    prom = client.get("/metrics/prometheus").text
    assert "futk_requests_total" in prom and "futk_uptime_seconds" in prom


def test_api_key_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("FUTK_API_KEYS", "secreta,outra")
    assert client.get("/matches").status_code == 401
    assert client.get("/health").status_code == 200  # exempt
    ok = client.get("/matches", headers={"X-API-Key": "secreta"})
    assert ok.status_code == 200
    bad = client.get("/matches", headers={"X-API-Key": "errada"})
    assert bad.status_code == 401


def test_open_when_no_keys_configured(client, monkeypatch):
    monkeypatch.delenv("FUTK_API_KEYS", raising=False)
    assert client.get("/matches").status_code == 200


def test_rate_limiter_bucket():
    rl = RateLimiter(limit=3, window=60)
    assert all(rl.allow("a")[0] for _ in range(3))
    blocked, retry = rl.allow("a")
    assert blocked is False and retry >= 1
    assert rl.allow("b")[0] is True  # per-caller isolation


def test_rate_limit_http_429(client, monkeypatch):
    # Rebuild the middleware limiter with a tiny limit via a fresh app? The
    # middleware reads env at startup; patch the live limiter instead.
    from app.main import app as fastapi_app

    for mw in fastapi_app.user_middleware:
        pass
    # Reach the instantiated middleware through the stack:
    stack = fastapi_app.middleware_stack
    node = stack
    limiter = None
    while node is not None:
        if hasattr(node, "limiter"):
            limiter = node.limiter
            break
        node = getattr(node, "app", None)
    assert limiter is not None, "SecurityMiddleware not found in stack"
    old = (limiter.limit, limiter.window)
    limiter.limit, limiter.window = 2, 60
    limiter._hits.clear()
    try:
        assert client.get("/matches").status_code == 200
        assert client.get("/matches").status_code == 200
        resp = client.get("/matches")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
    finally:
        limiter.limit, limiter.window = old
        limiter._hits.clear()
