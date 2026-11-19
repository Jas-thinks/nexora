"""The pieces that make several API replicas + several workers behave like one system."""
import threading
from datetime import timedelta

import pytest


from app.core import cache, leader, redis_client
from app.core import db as dbmod
from app.models.integrations import SyncJob
from app.services import ingest
from app.services.ingest import utcnow
from tests.conftest import auth, register


class FakeRedis:
    """Just enough of redis-py for cache, leader lease and rate limiter."""

    def __init__(self):
        self.d, self.exp, self.down = {}, {}, False

    def _chk(self):
        if self.down:
            raise ConnectionError("redis down")

    def get(self, k): self._chk(); return self.d.get(k)
    def set(self, k, v, nx=False, ex=None):
        self._chk()
        if nx and k in self.d:
            return None
        self.d[k] = v; return True
    def delete(self, k): self._chk(); self.d.pop(k, None)
    def scan_iter(self, match="*", count=100):
        self._chk(); pre = match.rstrip("*"); return [k for k in list(self.d) if k.startswith(pre)]
    def eval(self, script, n, key, inst, ms):
        self._chk(); return 1 if self.d.get(key) == inst else 0


def _use(monkeypatch, fake):
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "redis_url", "redis://fake")
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(leader, "get_redis", lambda: fake)
    monkeypatch.setattr(cache, "get_redis", lambda: fake)


# --- job queue: a job must never run twice -------------------------------------------------
def _job(db, **kw):
    j = SyncJob(kind="contests", platform="codeforces", status="queued", run_after=utcnow() - timedelta(seconds=1), **kw)
    db.add(j); db.commit(); return j.id


def test_claim_is_exclusive_sequential(client):
    with dbmod.SessionLocal() as db:
        jid = _job(db)
        assert ingest._claim(db, jid) is True
        assert ingest._claim(db, jid) is False  # already running: a second worker must not take it


def test_claim_is_exclusive_under_real_concurrency(client):
    if dbmod.engine.dialect.name != "postgresql":
        pytest.skip("needs separate connections per thread (SQLite :memory: shares one); runs on Postgres in CI")
    with dbmod.SessionLocal() as db:
        jid = _job(db)
    wins = []

    def go():
        with dbmod.SessionLocal() as db:
            wins.append(ingest._claim(db, jid))
    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert wins.count(True) == 1  # exactly one of six racing workers owns the job


def test_run_due_jobs_runs_each_once(client):
    calls = []

    class A:
        def fetch_contests(self):
            calls.append(1); return []
    with dbmod.SessionLocal() as db:
        _job(db); _job(db)
    with dbmod.SessionLocal() as w1, dbmod.SessionLocal() as w2:
        n1 = ingest.run_due_jobs(w1, adapter_factory=lambda p: A())
        n2 = ingest.run_due_jobs(w2, adapter_factory=lambda p: A())  # second worker finds nothing left
    assert (n1, n2) == (2, 0) and len(calls) == 2


def test_stale_running_job_is_requeued(client):
    with dbmod.SessionLocal() as db:
        j = SyncJob(kind="contests", platform="codeforces", status="running", attempts=1, started_at=utcnow() - timedelta(hours=2))
        db.add(j); db.commit(); jid = j.id
        assert ingest.reap_stale(db) == 1
        assert db.get(SyncJob, jid).status == "queued"


def test_stale_job_out_of_attempts_goes_dead(client):
    with dbmod.SessionLocal() as db:
        j = SyncJob(kind="contests", platform="codeforces", status="running", attempts=3, max_attempts=3, started_at=utcnow() - timedelta(hours=2))
        db.add(j); db.commit()
        ingest.reap_stale(db)
        assert db.get(SyncJob, j.id).status == "dead"


# --- leader election ----------------------------------------------------------------------
def test_only_one_instance_leads(client, monkeypatch):
    fake = FakeRedis(); _use(monkeypatch, fake)
    with dbmod.SessionLocal() as db:
        assert leader.try_lead(db) is True           # this process takes the lease
        monkeypatch.setattr(leader, "INSTANCE", "someone-else")
        assert leader.try_lead(db) is False          # a second instance does not
        monkeypatch.setattr(leader, "INSTANCE", leader.INSTANCE)


def test_unreachable_redis_elects_nobody(client, monkeypatch):
    _use(monkeypatch, None); monkeypatch.setattr(redis_client, "get_redis", lambda: None); monkeypatch.setattr(leader, "get_redis", lambda: None)
    with dbmod.SessionLocal() as db:
        assert leader.try_lead(db) is False  # a missed tick is harmless; a duplicated email is not


def test_no_redis_means_always_leader_on_sqlite(client):
    with dbmod.SessionLocal() as db:
        assert leader.try_lead(db) is True


# --- cache --------------------------------------------------------------------------------
def test_cache_reads_through_once(client):
    cache.clear_local(); n = []
    f = lambda: n.append(1) or {"v": len(n)}
    assert cache.cached("t:x", 60, f) == {"v": 1}
    assert cache.cached("t:x", 60, f) == {"v": 1} and len(n) == 1


def test_cache_shared_across_replicas_and_fails_open(client, monkeypatch):
    fake = FakeRedis(); _use(monkeypatch, fake); cache.clear_local()
    cache.put("t:y", {"a": 1}, 60)
    cache.clear_local()  # a different replica has an empty local copy
    assert cache.get("t:y") == {"a": 1}  # ...but sees the shared value
    fake.down = True; cache.clear_local()
    assert cache.get("t:y") is None  # redis down => miss, never an exception
    assert cache.cached("t:z", 60, lambda: 5) == 5


def test_invalidate_prefix(client, monkeypatch):
    fake = FakeRedis(); _use(monkeypatch, fake); cache.clear_local()
    cache.put("res:a", 1, 60); cache.put("other:b", 2, 60)
    cache.invalidate("res:")
    assert cache.get("res:a") is None and cache.get("other:b") == 2


def test_resources_overview_cache_is_not_per_user(client):
    cache.clear_local()
    a = register(client, "a@example.com"); b = register(client, "b@example.com")
    r1 = client.get("/resources/overview", headers=auth(a)); r2 = client.get("/resources/overview", headers=auth(b))
    assert r1.status_code == r2.status_code == 200 and r1.json()["tiers"] == r2.json()["tiers"]
    assert "you_solved" in r2.json()  # per-user field still computed per request


# --- liveness / readiness ----------------------------------------------------------------
def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok"
    assert r.headers["x-served-by"]  # the LB spread is observable


def test_ready_is_503_when_db_is_down(client, monkeypatch):
    class Boom:
        def connect(self): raise RuntimeError("db down")
    monkeypatch.setattr(dbmod, "engine", Boom())
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["status"] == "unready"
    assert client.get("/health").status_code == 200  # liveness unaffected: no restart loop for a DB blip


# --- against a REAL Redis (skipped when none is reachable): the fake above cannot catch a wrong command signature ----------
from tests.test_platform_hardening import REDIS_URL, _redis_up  # noqa: E402


@pytest.fixture()
def real_redis(monkeypatch):
    if not _redis_up():
        pytest.skip("real Redis required")
    import redis
    from app.core import config
    c = redis.Redis.from_url(REDIS_URL); c.flushall()
    monkeypatch.setattr(config.get_settings(), "redis_url", REDIS_URL)
    redis_client.drop()
    yield c
    redis_client.drop()


def test_real_redis_leader_lease_is_exclusive_and_renews(client, real_redis, monkeypatch):
    with dbmod.SessionLocal() as db:
        assert leader.try_lead(db) is True and leader.try_lead(db) is True   # acquire, then renew (Lua script path)
        monkeypatch.setattr(leader, "INSTANCE", "another-worker")
        assert leader.try_lead(db) is False
    assert 0 < real_redis.ttl("nx:leader:scheduler") <= leader.LEASE_S


def test_real_redis_cache_roundtrip_and_invalidate(client, real_redis):
    cache.clear_local()
    cache.put("res:k", {"a": [1, 2]}, 60)
    cache.clear_local()
    assert cache.get("res:k") == {"a": [1, 2]}
    assert 0 < real_redis.ttl("nx:v1:res:k") <= 60
    cache.invalidate("res:")
    assert cache.get("res:k") is None


def test_postgres_advisory_lock_leader(client):
    """Without Redis, Postgres elects the leader with a session advisory lock held on one dedicated connection."""
    import zlib

    from sqlalchemy import text
    if dbmod.engine.dialect.name != "postgresql":
        pytest.skip("Postgres only")
    leader._pg_conn = None
    key = leader.ADVISORY_KEY + zlib.crc32(b"t-lock")
    with dbmod.engine.connect() as other:                       # another process already leads
        assert other.execute(text("select pg_try_advisory_lock(:k)"), {"k": key}).scalar() is True
        with dbmod.SessionLocal() as db:
            assert leader.try_lead(db, "t-lock") is False
        other.execute(text("select pg_advisory_unlock(:k)"), {"k": key}); other.commit()
    with dbmod.SessionLocal() as db:                            # the leader died / released: we take over, and keep it (re-entrant)
        assert leader.try_lead(db, "t-lock") is True and leader.try_lead(db, "t-lock") is True
    leader._pg_conn.close(); leader._pg_conn = None
