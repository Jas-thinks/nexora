import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    """In-process limiter (default). Interface-compatible with RedisLimiter, which is used when CODEMIND_REDIS_URL is set."""

    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Too many requests", headers={"Retry-After": str(int(window))})
        q.append(now)


class RedisLimiter:
    """Shared sliding window across API instances (sorted set per key). Fails OPEN on Redis errors: an outage must not take the API down."""

    def __init__(self, client) -> None:
        self.r = client

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now = time.time()
        k = f"rl:{key}"
        try:
            pipe = self.r.pipeline()
            pipe.zremrangebyscore(k, 0, now - window); pipe.zcard(k)
            _, n = pipe.execute()
            if n >= limit:
                raise HTTPException(429, "Too many requests", headers={"Retry-After": str(int(window))})
            pipe = self.r.pipeline()
            pipe.zadd(k, {f"{now}:{time.monotonic_ns()}": now}); pipe.expire(k, int(window) + 1)
            pipe.execute()
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001 - Redis down => fall back to allowing the request
            return


class _Facade:
    """`limiter.check(...)` keeps working everywhere; the backend is chosen per call from the shared (self-healing) Redis client."""

    def __init__(self) -> None:
        self.local = SlidingWindowLimiter()

    @property
    def hits(self):  # tests clear this
        return self.local.hits

    def _backend(self):
        from app.core.redis_client import get_redis
        r = get_redis()
        return RedisLimiter(r) if r is not None else self.local

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        self._backend().check(key, limit, window)

    def reset_backend(self) -> None:
        from app.core import redis_client
        redis_client.drop()


limiter = _Facade()


def auth_rate_limit(request: Request) -> None:
    from app.core.config import get_settings
    ip = request.client.host if request.client else "unknown"
    limiter.check(f"auth:{ip}", get_settings().auth_rate_limit_per_minute)
