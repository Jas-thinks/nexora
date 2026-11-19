import os
import json

import pytest

from app.core import ratelimit
from app.core.config import get_settings
from tests.conftest import auth, register


def test_security_headers_request_id_and_no_store_on_auth(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY" and r.headers["Referrer-Policy"] == "no-referrer" and r.headers["X-Request-ID"] == "abc123"
    assert "Strict-Transport-Security" not in r.headers  # only in prod
    t = register(client)
    assert client.get("/auth/me", headers=auth(t)).headers["Cache-Control"] == "no-store"
    assert client.get("/health").headers["X-Request-ID"]  # generated when absent


def test_hsts_only_in_prod(monkeypatch):
    monkeypatch.setenv("CODEMIND_ENV", "prod"); monkeypatch.setenv("CODEMIND_JWT_SECRET", "x" * 40); get_settings.cache_clear()
    try:
        from fastapi.testclient import TestClient
        from app.main import create_app
        assert "max-age" in TestClient(create_app()).get("/health").headers["Strict-Transport-Security"]
    finally:
        get_settings.cache_clear()


def test_metrics_endpoint_requires_token_and_uses_route_templates(client, monkeypatch):
    assert client.get("/metrics").status_code == 401
    monkeypatch.setenv("CODEMIND_METRICS_TOKEN", "tok123"); get_settings.cache_clear()
    try:
        t = register(client); h = auth(t)
        client.get("/problems/1", headers=h); client.get("/problems/2", headers=h)
        assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        body = client.get("/metrics", headers={"Authorization": "Bearer tok123"}).text
        assert 'route="/problems/{pid}"' in body and 'route="/problems/1"' not in body  # bounded cardinality: templates, never raw ids
        assert "nexora_http_request_seconds_bucket" in body and "nexora_llm_tokens_total" in body
    finally:
        get_settings.cache_clear()


def test_json_log_formatter_and_no_secrets_in_access_log(client, caplog):
    import logging
    from app.core.observability import JsonFormatter
    rec = logging.LogRecord("nexora.access", logging.INFO, "f", 1, "request", None, None); rec.extra_fields = {"route": "/x", "status": 200}
    d = json.loads(JsonFormatter().format(rec))
    assert d["msg"] == "request" and d["route"] == "/x" and d["status"] == 200


# ---------------------------------------------------------------- rate limiter backends
class FakeRedis:
    def __init__(self): self.z = {}
    def pipeline(self): return FakePipe(self)


class FakePipe:
    def __init__(self, r): self.r, self.ops = r, []
    def zremrangebyscore(self, k, lo, hi): self.ops.append(("rem", k, lo, hi)); return self
    def zcard(self, k): self.ops.append(("card", k)); return self
    def zadd(self, k, m): self.ops.append(("add", k, m)); return self
    def expire(self, k, s): return self
    def execute(self):
        out = []
        for op in self.ops:
            if op[0] == "rem":
                d = self.r.z.setdefault(op[1], {}); [d.pop(m) for m, sc in list(d.items()) if op[2] <= sc <= op[3]]; out.append(0)
            elif op[0] == "card": out.append(len(self.r.z.get(op[1], {})))
            elif op[0] == "add": self.r.z.setdefault(op[1], {}).update(op[2]); out.append(1)
        self.ops = []; return out


def test_redis_limiter_enforces_a_shared_window_and_fails_open():
    from fastapi import HTTPException
    lim = ratelimit.RedisLimiter(FakeRedis())
    for _ in range(3): lim.check("k", 3, 60)
    with pytest.raises(HTTPException) as e:
        lim.check("k", 3, 60)
    assert e.value.status_code == 429
    class Dead:
        def pipeline(self): raise ConnectionError("down")
    ratelimit.RedisLimiter(Dead()).check("k", 1, 60)  # no exception: outage must not block users


REDIS_URL = os.environ.get("NEXORA_TEST_REDIS", "redis://localhost:56379")  # CI provides a Redis service; locally: docker run -p 56379:6379 redis:7-alpine


def _redis_up():
    try:
        import redis
        r = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.3); r.ping(); return True
    except Exception:
        return False


@pytest.mark.skipif(not _redis_up(), reason="real Redis required (NEXORA_TEST_REDIS, default :56379)")
def test_real_redis_limiter_is_shared_between_two_instances():
    import redis
    from fastapi import HTTPException
    c = redis.Redis.from_url(REDIS_URL); c.flushall()
    a, b = ratelimit.RedisLimiter(c), ratelimit.RedisLimiter(redis.Redis.from_url(REDIS_URL))  # two "API instances"
    a.check("shared", 2, 30); b.check("shared", 2, 30)
    with pytest.raises(HTTPException):
        a.check("shared", 2, 30)
