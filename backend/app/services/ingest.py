"""Ingestion: adapter output -> normalized tables. Idempotent, incremental, provenance-tagged."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.integrations.adapters import ADAPTERS, PlatformAdapter
from app.integrations.http import FetchError
from app.integrations.registry import BY_SLUG
from app.integrations.types import NormContest, NormProblem, NormRating, NormSubmission, NotSupported
from app.models.catalog import Problem, ProblemStatus
from app.models.integrations import ConnectedProfile, Contest, RatingHistory, Submission, SyncJob
from app.models.user import utcnow


def get_adapter(platform: str, **kw) -> PlatformAdapter:
    cls = ADAPTERS.get(platform)
    if cls is None:
        raise NotSupported(f"No adapter for '{platform}'")
    return cls(**kw)


def _canon_url(platform: str, ext: str) -> str | None:
    return None


def _utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC so comparisons are stable across backends."""
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))


def upsert_problems(db: Session, platform: str, items: list[NormProblem]) -> dict:
    existing = {p.external_id: p for p in db.scalars(select(Problem).where(Problem.platform == platform))}
    added = updated = 0
    for it in items:
        row = existing.get(it.external_id)
        if row is None:
            db.add(Problem(platform=platform, external_id=it.external_id, name=it.name, rating=it.rating,
                           tags=sorted(it.tags), url=it.url, canonical_url=it.url, source_difficulty=it.source_difficulty))
            added += 1
        else:
            new = (it.name, it.rating, sorted(it.tags), it.source_difficulty)
            if (row.name, row.rating, row.tags, row.source_difficulty) != new:
                row.name, row.rating, row.tags, row.source_difficulty = new
                updated += 1
    db.commit()
    from app.patterns.mastery import bump_catalog
    bump_catalog()
    return {"added": added, "updated": updated, "total": len(items)}


def upsert_contests(db: Session, platform: str, items: list[NormContest]) -> dict:
    existing = {c.external_id: c for c in db.scalars(select(Contest).where(Contest.platform == platform))}
    added = updated = 0
    now = utcnow()
    for it in items:
        row = existing.get(it.external_id)
        if row is None:
            db.add(Contest(platform=platform, external_id=it.external_id, name=it.name, start_time=it.start_time,
                           duration_seconds=it.duration_seconds, url=it.url, rated=it.rated, source=it.source, synced_at=now))
            added += 1
        else:
            if (row.name, _utc(row.start_time), row.duration_seconds) != (it.name, _utc(it.start_time), it.duration_seconds):
                updated += 1
            row.name, row.start_time, row.duration_seconds, row.url, row.rated, row.source, row.synced_at = (
                it.name, it.start_time, it.duration_seconds, it.url, it.rated, it.source, now)
    db.commit()
    return {"added": added, "updated": updated, "total": len(items)}


def store_submissions(db: Session, profile: ConnectedProfile, subs: list[NormSubmission]) -> dict:
    keys = {(s.external_id) for s in subs}
    have = set(db.scalars(select(Submission.external_id).where(
        Submission.user_id == profile.user_id, Submission.platform == profile.platform, Submission.external_id.in_(keys)))) if keys else set()
    probs = {p.external_id: p.id for p in db.scalars(select(Problem).where(Problem.platform == profile.platform))}
    added = dup = 0
    for s in subs:
        if s.external_id in have:
            dup += 1; continue
        db.add(Submission(user_id=profile.user_id, profile_id=profile.id, platform=profile.platform, external_id=s.external_id,
                          problem_id=probs.get(s.problem_ref), problem_ref=s.problem_ref, verdict=s.verdict, raw_verdict=s.raw_verdict,
                          language=s.language, submitted_at=s.submitted_at, time_ms=s.time_ms, memory_kb=s.memory_kb,
                          in_contest=s.in_contest, provenance=s.provenance))
        added += 1
    db.commit()
    return {"added": added, "duplicates": dup}


def store_ratings(db: Session, profile: ConnectedProfile, rows: list[NormRating]) -> dict:
    have = set(db.scalars(select(RatingHistory.contest_ref).where(RatingHistory.user_id == profile.user_id,
                                                                  RatingHistory.platform == profile.platform)))
    added = 0
    for r in rows:
        if r.contest_ref in have:
            continue
        db.add(RatingHistory(user_id=profile.user_id, profile_id=profile.id, platform=profile.platform, contest_ref=r.contest_ref,
                             contest_name=r.contest_name, at=r.at, old_rating=r.old_rating, new_rating=r.new_rating,
                             rank=r.rank, performance=r.performance))
        added += 1
    db.commit()
    return {"added": added, "total": len(rows)}


def refresh_progress_from_submissions(db: Session, user_id: int) -> int:
    """Verified AC submissions upgrade ProblemStatus to 'verified_submission' (verified wins over self-report)."""
    rows = db.execute(select(Submission.problem_id, Submission.verdict, Submission.submitted_at, Submission.provenance)
                      .where(Submission.user_id == user_id, Submission.problem_id.is_not(None))).all()
    agg: dict[int, dict] = {}
    for pid, verdict, at, prov in rows:
        a = agg.setdefault(pid, {"attempts": 0, "first_ac": None, "prov": "verified_submission"})
        a["attempts"] += 1
        if prov != "verified":
            a["prov"] = "user_import"
        if verdict == "AC" and (a["first_ac"] is None or at < a["first_ac"]):
            a["first_ac"] = at
    changed = 0
    for pid, a in agg.items():
        st = db.scalar(select(ProblemStatus).where(ProblemStatus.user_id == user_id, ProblemStatus.problem_id == pid))
        if st is None:
            st = ProblemStatus(user_id=user_id, problem_id=pid); db.add(st)
        st.attempts = max(st.attempts or 0, a["attempts"])
        if a["first_ac"] is not None:
            st.solved, st.first_solved_at, st.provenance = True, a["first_ac"], a["prov"]
        changed += 1
    db.commit()
    return changed


def sync_profile(db: Session, profile: ConnectedProfile, adapter: PlatformAdapter | None = None) -> dict:
    """Run one incremental sync for a connected profile. Raises FetchError (retryable or not) on failure."""
    info = BY_SLUG[profile.platform]
    adapter = adapter or get_adapter(profile.platform)
    stats: dict = {}
    if "submissions" in info.capabilities:
        page = adapter.fetch_submissions(profile.handle, profile.checkpoint or {})
        stats["submissions"] = store_submissions(db, profile, page.items) | {"skipped_unjudged": page.skipped}
        profile.checkpoint = {**(profile.checkpoint or {}), **page.checkpoint}
    if "rating_history" in info.capabilities:
        stats["ratings"] = store_ratings(db, profile, adapter.fetch_rating_history(profile.handle))
    profile.status, profile.last_error, profile.last_synced_at, profile.data_level = "ok", None, utcnow(), "public_api"
    db.commit()
    stats["progress_rows"] = refresh_progress_from_submissions(db, profile.user_id)
    from app.services.recommender import rebuild_mastery
    rebuild_mastery(db, profile.user_id)
    from app.services.daily import verify_solves
    stats["daily_verified"] = verify_solves(db, profile.user_id)
    from app.services.mistakes import enroll_recovered
    stats["revision_enrolled"] = enroll_recovered(db, profile.user_id)
    return stats


# ------------------------------------------------------------ job queue (DB-backed; Redis/Celery later)
def enqueue(db: Session, kind: str, platform: str, user_id: int | None = None, profile_id: int | None = None) -> SyncJob:
    dup = db.scalar(select(SyncJob).where(SyncJob.kind == kind, SyncJob.platform == platform, SyncJob.profile_id == profile_id,
                                          SyncJob.status.in_(("queued", "running"))))
    if dup:  # idempotent enqueue: one live job per target
        return dup
    job = SyncJob(kind=kind, platform=platform, user_id=user_id, profile_id=profile_id)
    db.add(job); db.commit()
    return job


def run_job(db: Session, job: SyncJob, adapter: PlatformAdapter | None = None) -> SyncJob:
    job.status, job.started_at, job.attempts = "running", utcnow(), job.attempts + 1
    db.commit()
    try:
        ad = adapter or get_adapter(job.platform)
        if job.kind == "profile_sync":
            profile = db.get(ConnectedProfile, job.profile_id)
            if profile is None:
                raise NotSupported("profile was removed")
            job.stats = sync_profile(db, profile, ad)
        elif job.kind == "contests":
            job.stats = upsert_contests(db, job.platform, ad.fetch_contests())
        elif job.kind == "backfill":
            from app.sources.backfill import run_backfill, run_details
            from app.sources.sources import SOURCES
            src = SOURCES[job.platform]()
            job.stats = run_backfill(db, src)
            if job.stats["status"] == "interrupted":
                raise FetchError(job.stats["error"] or "interrupted", retryable=True)  # job backoff retries; checkpoint resumes
            if job.platform == "dmoj":
                job.stats["details"] = run_details(db, src, limit=100)
        elif job.kind == "problems":
            job.stats = upsert_problems(db, job.platform, ad.fetch_problem_metadata())
        else:
            raise NotSupported(f"unknown job kind {job.kind}")
        job.status, job.error, job.finished_at = "succeeded", None, utcnow()
    except NotSupported as e:  # permanent: do not retry
        job.status, job.error, job.finished_at = "dead", f"unsupported: {e}", utcnow()
    except FetchError as e:
        job.error = str(e)[:900]
        if e.retryable and job.attempts < job.max_attempts:
            job.status, job.run_after = "queued", utcnow() + timedelta(seconds=30 * 2 ** (job.attempts - 1))
        else:
            job.status, job.finished_at = ("dead" if e.retryable else "failed"), utcnow()  # dead = retries exhausted
        if job.profile_id and (p := db.get(ConnectedProfile, job.profile_id)):
            p.status, p.last_error = "error", job.error
    db.commit()
    return job


STALE_RUNNING = timedelta(minutes=30)


def reap_stale(db: Session) -> int:
    """A worker that died mid-job leaves it 'running' forever. Requeue those (or mark dead when attempts are exhausted)."""
    cutoff = utcnow() - STALE_RUNNING
    n = 0
    for j in db.scalars(select(SyncJob).where(SyncJob.status == "running", SyncJob.started_at < cutoff)):
        j.status, j.error = ("queued" if j.attempts < j.max_attempts else "dead"), "worker stopped before finishing"
        j.run_after = utcnow()
        n += 1
    if n:
        db.commit()
    return n


def _claim(db: Session, job_id: int) -> bool:
    """Atomically move queued -> running. With several workers only ONE gets rowcount 1, so a job never runs twice."""
    res = db.execute(update(SyncJob).where(SyncJob.id == job_id, SyncJob.status == "queued").values(status="running", started_at=utcnow()))
    db.commit()
    return res.rowcount == 1


def run_due_jobs(db: Session, limit: int = 10, adapter_factory=None) -> int:
    reap_stale(db)
    now = utcnow()
    ids = db.scalars(select(SyncJob.id).where(SyncJob.status == "queued", SyncJob.run_after <= now).order_by(SyncJob.id).limit(limit)).all()
    ran = 0
    for jid in ids:
        if not _claim(db, jid):
            continue  # another worker took it
        j = db.get(SyncJob, jid)
        db.refresh(j)
        run_job(db, j, adapter_factory(j.platform) if adapter_factory else None)
        ran += 1
    return ran
