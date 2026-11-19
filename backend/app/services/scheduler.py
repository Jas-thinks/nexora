"""Periodic refresh: enqueue jobs for stale data. Idempotent (enqueue returns an existing live job), bounded per tick, and polite
(profile syncs are spread: at most N per tick so platform rate limits are respected)."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.registry import BY_SLUG
from app.models.catalog import SyncCheckpoint
from app.models.integrations import ConnectedProfile, Contest
from app.services import ingest
from app.sources.sources import SOURCES

PROFILE_STALE = timedelta(hours=24)
CONTEST_STALE = timedelta(hours=12)
CATALOG_STALE = timedelta(days=7)


def _aw(d):
    return None if d is None else (d if d.tzinfo else d.replace(tzinfo=UTC))


def tick(db: Session, now: datetime | None = None, max_profiles: int = 5) -> dict:
    now = now or datetime.now(UTC)
    out = {"profiles": 0, "contests": 0, "catalog": 0}
    stale = []
    for p in db.scalars(select(ConnectedProfile).where(ConnectedProfile.data_level == "public_api")):
        info = BY_SLUG.get(p.platform)
        if not info or "submissions" not in info.capabilities:
            continue
        last = _aw(p.last_synced_at)
        if last is None or now - last > PROFILE_STALE:
            stale.append((last or datetime.min.replace(tzinfo=UTC), p))
    for _, p in sorted(stale, key=lambda x: x[0])[:max_profiles]:  # oldest first; the rest wait for the next tick
        ingest.enqueue(db, "profile_sync", p.platform, p.user_id, p.id); out["profiles"] += 1
    last_c = {r[0]: _aw(r[1]) for r in db.execute(select(Contest.platform, func.max(Contest.synced_at)).group_by(Contest.platform))}
    for plat in ("codeforces", "atcoder", "dmoj", "codechef"):
        if plat in last_c and now - last_c[plat] > CONTEST_STALE:
            ingest.enqueue(db, "contests", plat); out["contests"] += 1
    for cp in db.scalars(select(SyncCheckpoint).where(SyncCheckpoint.stage == "enumerate", SyncCheckpoint.done.is_(True))):
        if cp.platform in SOURCES and cp.completed_at and now - _aw(cp.completed_at) > CATALOG_STALE:
            ingest.enqueue(db, "backfill", cp.platform); out["catalog"] += 1
    return out
