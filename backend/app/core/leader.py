"""Leader election for work that must run on ONE instance at a time (the periodic scheduler and notification ticks).

Without it, N workers would each enqueue refreshes and send the same notification email N times. Uses a Redis lease when Redis is
configured, a Postgres advisory lock on Postgres, and is always-leader on SQLite (single process, dev). If Redis is configured but
unreachable we do NOT elect everyone: a missed tick is harmless, a duplicated email is not."""
import uuid
import zlib

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis_client import get_redis

INSTANCE = uuid.uuid4().hex
LEASE_S = 90
ADVISORY_KEY = 7_424_000

_RENEW = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('pexpire',KEYS[1],ARGV[2]) else return 0 end"


def try_lead(db: Session, name: str = "scheduler", lease_s: int = LEASE_S) -> bool:
    """True when this instance holds (or just acquired) the lease for `name`. Call before each tick; it renews itself."""
    s = get_settings()
    if s.redis_url:
        r = get_redis()
        if r is None:
            return False
        key = f"nx:leader:{name}"
        try:
            if r.set(key, INSTANCE, nx=True, ex=lease_s):
                return True
            return bool(r.eval(_RENEW, 1, key, INSTANCE, lease_s * 1000))
        except Exception:  # noqa: BLE001
            return False
    if db.get_bind().dialect.name == "postgresql":
        return _pg_lead(db, name)
    return True


_pg_conn = None


def _pg_lead(db: Session, name: str) -> bool:
    """Session-level advisory lock held on ONE dedicated connection for the life of the process (the pool would hand out different
    connections, silently dropping a session lock). The lock vanishes with the connection, so a crashed leader is replaced automatically."""
    global _pg_conn
    key = ADVISORY_KEY + zlib.crc32(name.encode())  # stable across processes (str hash() is randomised per process)
    try:
        if _pg_conn is None or _pg_conn.closed:
            _pg_conn = db.get_bind().connect()
        got = bool(_pg_conn.execute(text("select pg_try_advisory_lock(:k)"), {"k": key}).scalar())
        _pg_conn.commit()
        return got
    except Exception:  # noqa: BLE001 - connection lost: the lock is gone with it; try again next tick
        try:
            if _pg_conn is not None:
                _pg_conn.close()
        finally:
            _pg_conn = None
        return False
