"""Read-through cache for hot, user-independent data (company lists, design-question library, aggregates).

Redis when configured (shared by every API replica, so a warm cache survives a replica restart and is consistent across the fleet),
a small in-process TTL map otherwise. Fails OPEN: any Redis error just means a cache miss. Values must be JSON-serialisable.
Never cache anything that depends on the caller: put the per-user part outside the cached function."""
import json
import threading
import time
from collections.abc import Callable
from typing import Any

from prometheus_client import Counter

from app.core.redis_client import get_redis

HITS = Counter("nexora_cache_requests_total", "Cache lookups", ["result"])  # hit | miss
NS = "nx:v1:"
MAX_LOCAL = 512

_local: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()


def _local_get(key: str):
    with _lock:
        e = _local.get(key)
        if e and e[0] > time.monotonic():
            return e[1]
        _local.pop(key, None)
    return None


def _local_set(key: str, raw: str, ttl: float) -> None:
    with _lock:
        if len(_local) >= MAX_LOCAL:
            now = time.monotonic()
            for k in [k for k, v in _local.items() if v[0] <= now] or list(_local)[: MAX_LOCAL // 4]:
                _local.pop(k, None)
        _local[key] = (time.monotonic() + ttl, raw)


def get(key: str) -> Any | None:
    r = get_redis()
    raw = None
    if r is not None:
        try:
            raw = r.get(NS + key)
        except Exception:  # noqa: BLE001
            raw = None
    if raw is None:
        raw = _local_get(key)
    if raw is None:
        return None
    return json.loads(raw)


def put(key: str, value: Any, ttl: int) -> None:
    raw = json.dumps(value, default=str)
    _local_set(key, raw, min(ttl, 30))  # local copy is a short-lived L1 so a Redis outage still helps without serving stale data for long
    r = get_redis()
    if r is not None:
        try:
            r.set(NS + key, raw, ex=ttl)
        except Exception:  # noqa: BLE001
            pass


def cached(key: str, ttl: int, fn: Callable[[], Any]) -> Any:
    v = get(key)
    if v is not None:
        HITS.labels("hit").inc()
        return v
    HITS.labels("miss").inc()
    v = fn()
    put(key, v, ttl)
    return v


def invalidate(prefix: str) -> None:
    with _lock:
        for k in [k for k in _local if k.startswith(prefix)]:
            _local.pop(k, None)
    r = get_redis()
    if r is not None:
        try:
            for k in r.scan_iter(match=f"{NS}{prefix}*", count=200):
                r.delete(k)
        except Exception:  # noqa: BLE001
            pass


def clear_local() -> None:
    with _lock:
        _local.clear()
