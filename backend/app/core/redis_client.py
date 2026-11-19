"""One lazily-created Redis connection shared by the rate limiter, the cache and the leader lock.

Redis is an optimisation, never a dependency: with no CODEMIND_REDIS_URL (or when Redis is down) callers get None and fall back to
in-process behaviour. A failed connect is retried after a short cooldown so an API that boots before Redis is healthy recovers
by itself instead of staying degraded until it is restarted."""
import threading
import time

from app.core.config import get_settings

RETRY_AFTER_S = 15.0
_lock = threading.Lock()
_client = None
_next_try = 0.0


def get_redis():
    global _client, _next_try
    url = get_settings().redis_url
    if not url:
        return None
    if _client is not None:
        return _client
    now = time.monotonic()
    if now < _next_try:
        return None
    with _lock:
        if _client is not None:
            return _client
        try:
            import redis
            c = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5, health_check_interval=30)
            c.ping()
            _client = c
        except Exception:  # noqa: BLE001 - Redis is optional
            _client, _next_try = None, now + RETRY_AFTER_S
        return _client


def drop() -> None:
    """Forget the connection (tests, or after an error) so the next call reconnects."""
    global _client, _next_try
    _client, _next_try = None, 0.0
