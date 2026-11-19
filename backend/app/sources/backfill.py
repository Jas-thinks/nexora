"""Checkpointed, resumable, idempotent problem backfill + reconciliation + detail enrichment."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.http import FetchError
from app.models.catalog import Problem, ProblemStatisticsSnapshot, SyncCheckpoint, SyncFailure
from app.models.user import utcnow
from app.sources.base import ProblemRecord, ProblemSource

TRACKED = ("name", "url", "rating", "source_difficulty", "tags", "contest_ref", "problem_index", "time_limit_ms", "memory_limit_kb")


def _utc(d):
    """Always UTC. Sources may publish other offsets (yukicoder is +09:00) and SQLite drops offsets on storage, so store/compare in UTC."""
    return None if d is None else (d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC))


def _failure(db: Session, platform: str, stage: str, ref: str, err: str) -> None:
    f = db.scalar(select(SyncFailure).where(SyncFailure.platform == platform, SyncFailure.stage == stage, SyncFailure.ref == ref, SyncFailure.resolved.is_(False)))
    if f:
        f.attempts, f.error, f.last_at = f.attempts + 1, err[:600], utcnow()
    else:
        db.add(SyncFailure(platform=platform, stage=stage, ref=ref, error=err[:600]))
    db.commit()


def _upsert(db: Session, existing: dict[str, Problem], recs: list[ProblemRecord], source: str, now: datetime) -> dict:
    added = updated = unchanged = snaps = 0
    for r in recs:
        p = existing.get(r.external_id)
        vals = {k: getattr(r, k) for k in TRACKED}
        vals["tags"] = sorted(r.tags)
        if p is None:
            p = Problem(platform=r.platform, external_id=r.external_id, canonical_url=r.url, status="active", statement_access="link_only",
                        published_at=_utc(r.published_at), **vals)
            db.add(p); existing[r.external_id] = p; added += 1
        else:
            changed = False
            for k, v in vals.items():
                if k in ("time_limit_ms", "memory_limit_kb", "contest_ref", "problem_index", "rating", "source_difficulty") and v is None:
                    continue  # never erase a field a richer stage already filled
                if getattr(p, k) != v:
                    setattr(p, k, v); changed = True
            if r.published_at and _utc(p.published_at) != _utc(r.published_at):
                p.published_at = _utc(r.published_at); changed = True
            if p.status != "active":
                p.status = "active"; changed = True  # reappeared upstream
            if p.canonical_url is None:
                p.canonical_url = r.url
            updated, unchanged = (updated + 1, unchanged) if changed else (updated, unchanged + 1)
        p.source, p.observed_at = source, now
        if r.raw is not None and p.source_record != r.raw:
            p.source_record = r.raw
        if r.solved_count is not None or r.submission_count is not None:
            if (p.solved_count, p.submission_count) != (r.solved_count, r.submission_count):
                db.flush()
                db.add(ProblemStatisticsSnapshot(problem_id=p.id, observed_at=now, source=source, solved_count=r.solved_count,
                                                 submission_count=r.submission_count, accepted_count=r.accepted_count))
                p.solved_count, p.submission_count = r.solved_count, r.submission_count; snaps += 1
    return {"added": added, "updated": updated, "unchanged": unchanged, "snapshots": snaps}


def run_backfill(db: Session, src: ProblemSource, max_pages: int | None = None, restart: bool = False) -> dict:
    """Enumerate the source from its checkpoint. Safe to interrupt at any page boundary and to re-run (refresh when a prior pass completed)."""
    cp = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.platform == src.platform, SyncCheckpoint.stage == "enumerate"))
    now = utcnow()
    if cp is None:
        cp = SyncCheckpoint(platform=src.platform, stage="enumerate", cursor={}, started_at=now); db.add(cp)
    elif cp.done or restart:  # a finished pass => start a fresh refresh pass
        cp.cursor, cp.done, cp.retrieved, cp.started_at, cp.completed_at = {}, False, 0, now, None
    db.commit()
    existing = {p.external_id: p for p in db.scalars(select(Problem).where(Problem.platform == src.platform))}
    tot = {"added": 0, "updated": 0, "unchanged": 0, "snapshots": 0}
    pages, status, error = 0, "complete", None
    try:
        for recs, nxt in src.pages(cp.cursor or None):
            r = _upsert(db, existing, recs, src.source_name, utcnow())
            for k in tot: tot[k] += r[k]
            cp.cursor, cp.retrieved, cp.updated_at = nxt or {}, cp.retrieved + len(recs), utcnow()
            if src.discovered_total is not None:
                cp.discovered = src.discovered_total
            db.commit()  # checkpoint is committed together with the page's data
            pages += 1
            if nxt is None:
                break
            if max_pages is not None and pages >= max_pages:
                status = "partial"; break
        else:
            pass
    except FetchError as e:
        db.rollback(); status, error = "interrupted", str(e)
        _failure(db, src.platform, "enumerate", f"cursor={cp.cursor}", str(e))
    unseen = 0
    if status == "complete":
        cp = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.platform == src.platform, SyncCheckpoint.stage == "enumerate"))
        cp.done, cp.completed_at = True, utcnow()
        if src.complete_enumeration:  # reconciliation: anything this full pass did not observe is no longer listed upstream
            started = _utc(cp.started_at)
            for p in existing.values():
                if p.status == "active" and (p.observed_at is None or _utc(p.observed_at) < started):
                    p.status = "missing_upstream"; unseen += 1
        db.commit()
    from app.patterns.mastery import bump_catalog
    bump_catalog()
    return {"platform": src.platform, "status": status, "pages": pages, "retrieved": cp.retrieved, "discovered": cp.discovered or None,
            "missing_upstream_marked": unseen, "error": error, **tot}


def run_details(db: Session, src: ProblemSource, limit: int = 200) -> dict:
    """Stage 2: per-problem detail fetch for records still lacking limits. Query-based resume; failures isolated per problem."""
    todo = db.scalars(select(Problem).where(Problem.platform == src.platform, Problem.status == "active", Problem.time_limit_ms.is_(None))
                      .order_by(Problem.id).limit(limit)).all()
    ok = failed = 0
    for p in todo:
        try:
            r = src.details(p.external_id)
        except FetchError as e:
            _failure(db, src.platform, "details", p.external_id, str(e)); failed += 1
            if e.status == 404:
                p.status = "inaccessible"; db.commit()
            continue
        if r:
            p.time_limit_ms, p.memory_limit_kb = r.time_limit_ms, r.memory_limit_kb
            p.source_record = r.raw; p.observed_at = utcnow(); ok += 1
            db.commit()
    return {"platform": src.platform, "attempted": len(todo), "fetched": ok, "failed": failed}
