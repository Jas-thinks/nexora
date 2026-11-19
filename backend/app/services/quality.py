"""Data-quality report: measurable facts about the ingested data, stored for trend tracking."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, Sheet, SheetItem
from app.models.integrations import ConnectedProfile, Contest, DataQualityReport, Submission, SyncJob


def build_report(db: Session, persist: bool = True) -> dict:
    c = lambda stmt: db.scalar(stmt) or 0
    now = datetime.now(UTC)
    problems = c(select(func.count()).select_from(Problem))
    by_platform = dict(db.execute(select(Problem.platform, func.count()).group_by(Problem.platform)).all())
    subs = c(select(func.count()).select_from(Submission))
    unlinked = c(select(func.count()).select_from(Submission).where(Submission.problem_id.is_(None)))
    sheets = []
    for s in db.scalars(select(Sheet)):
        rep = s.import_report or {}
        n = c(select(func.count()).select_from(SheetItem).where(SheetItem.sheet_id == s.id))
        sheets.append({"slug": s.slug, "items": n, "invalid_urls": len(rep.get("invalid_urls", [])),
                       "duplicates_in_source": len(rep.get("duplicates_in_sheet", [])),
                       "skipped_no_problem_link": len(rep.get("skipped_no_problem_link", [])),
                       "imported_at": s.imported_at.isoformat() if s.imported_at else None, "source_url": s.source_url})
    stale = c(select(func.count()).select_from(ConnectedProfile).where(
        (ConnectedProfile.last_synced_at.is_(None)) | (ConnectedProfile.last_synced_at < (now - timedelta(days=7)).replace(tzinfo=None))))
    m = {
        "problems_total": problems, "problems_by_platform": by_platform,
        "problems_without_rating": c(select(func.count()).select_from(Problem).where(Problem.rating.is_(None))),
        "problems_without_tags": c(select(func.count()).select_from(Problem).where(cast(Problem.tags, String) == "[]")),
        "submissions_total": subs, "submissions_unlinked_to_catalog": unlinked,
        "submission_link_rate": round(1 - unlinked / subs, 4) if subs else None,
        "contests_total": c(select(func.count()).select_from(Contest)),
        "contests_without_start": c(select(func.count()).select_from(Contest).where(Contest.start_time.is_(None))),
        "profiles_total": c(select(func.count()).select_from(ConnectedProfile)), "profiles_stale_or_never_synced": stale,
        "jobs_dead": c(select(func.count()).select_from(SyncJob).where(SyncJob.status == "dead")),
        "jobs_failed": c(select(func.count()).select_from(SyncJob).where(SyncJob.status == "failed")),
        "sheets": sheets,
        "notes": ["Unrated != zero: ratings/tags are reported as missing, never filled in.",
                  "Submissions unlinked to the catalog keep their problem_ref and are counted here, not dropped."],
    }
    if persist:
        db.add(DataQualityReport(scope="global", metrics=m)); db.commit()
    return m
