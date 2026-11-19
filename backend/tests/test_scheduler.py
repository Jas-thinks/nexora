from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core import db as dbmod
from app.models.catalog import SyncCheckpoint
from app.models.integrations import ConnectedProfile, Contest, SyncJob
from app.models.user import User
from app.services import scheduler
from tests.conftest import register

NOW = datetime(2026, 6, 15, 12, tzinfo=UTC)


def jobs(db): return [(j.kind, j.platform) for j in db.scalars(select(SyncJob).order_by(SyncJob.id))]


def test_stale_profiles_are_enqueued_oldest_first_bounded_and_idempotent(client):
    register(client)
    with dbmod.SessionLocal() as db:
        uid = db.scalar(select(User.id))
        for i, age in enumerate((30, 50, 2, 70, 40, 90, 10)):  # hours since last sync
            db.add(ConnectedProfile(user_id=uid, platform="codeforces", handle=f"h{i}", data_level="public_api", last_synced_at=NOW - timedelta(hours=age)))
        db.add(ConnectedProfile(user_id=uid, platform="leetcode", handle="x", data_level="link_only"))  # never auto-synced
        db.add(ConnectedProfile(user_id=uid, platform="codeforces", handle="never", data_level="public_api", last_synced_at=None)); db.commit()
        r = scheduler.tick(db, NOW, max_profiles=3)
        assert r["profiles"] == 3
        handles = [db.get(ConnectedProfile, j.profile_id).handle for j in db.scalars(select(SyncJob).order_by(SyncJob.id))]
        assert handles[0] == "never" and handles[1:] == ["h5", "h3"]  # never-synced first, then oldest
        scheduler.tick(db, NOW, max_profiles=3)
        assert db.scalar(select(func.count(func.distinct(SyncJob.profile_id))).select_from(SyncJob)) <= 6


def test_contests_and_catalog_refresh_only_when_stale(client):
    with dbmod.SessionLocal() as db:
        db.add(Contest(platform="dmoj", external_id="a", name="a", url="u", source="t", synced_at=NOW - timedelta(hours=20)))
        db.add(Contest(platform="atcoder", external_id="b", name="b", url="u", source="t", synced_at=NOW - timedelta(hours=1)))
        db.add(SyncCheckpoint(platform="codechef", stage="enumerate", done=True, completed_at=NOW - timedelta(days=10)))
        db.add(SyncCheckpoint(platform="cses", stage="enumerate", done=True, completed_at=NOW - timedelta(days=1)))
        db.add(SyncCheckpoint(platform="yukicoder", stage="enumerate", done=False, completed_at=None)); db.commit()
        r = scheduler.tick(db, NOW)
        assert r == {"profiles": 0, "contests": 1, "catalog": 1} and set(jobs(db)) == {("contests", "dmoj"), ("backfill", "codechef")}
