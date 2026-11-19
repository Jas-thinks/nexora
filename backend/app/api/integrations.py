from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.importers import neetcode, takeuforward
from app.importers.registry import SHEET_SOURCES
from app.integrations import adapters
from app.integrations.http import FetchError
from app.integrations.registry import BY_SLUG, DATA_LEVELS, DISCOVERY_SOURCES, matrix
from app.models.catalog import Problem, ProblemStatus, Sheet, SheetItem
from app.models.integrations import ConnectedProfile, Contest, SyncJob
from app.models.user import User
from app.services import ingest, sheet_import

router = APIRouter(tags=["integrations"])


@router.get("/platforms")
def platforms():
    return {"platforms": matrix(), "data_levels": DATA_LEVELS, "discovery_leads_not_yet_crawled": DISCOVERY_SOURCES}


@router.get("/sheet-sources")
def sheet_sources():
    return SHEET_SOURCES


def _prof(p: ConnectedProfile) -> dict:
    info = BY_SLUG[p.platform]
    return {"id": p.id, "platform": p.platform, "name": info.name, "handle": p.handle, "data_level": p.data_level, "status": p.status,
            "last_synced_at": p.last_synced_at, "last_error": p.last_error, "capabilities": sorted(info.capabilities),
            "integration_status": info.status,
            "history_limitations": info.limitations or "No verified history capability; manual import only."}


class LinkIn(BaseModel):
    platform: str
    handle: str = Field(min_length=1, max_length=120, pattern=r"^[\w.\-@]+$")


@router.get("/profiles")
def list_profiles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_prof(p) for p in db.scalars(select(ConnectedProfile).where(ConnectedProfile.user_id == user.id))]


@router.post("/profiles", status_code=201)
def link_profile(body: LinkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    info = BY_SLUG.get(body.platform)
    if info is None:
        raise HTTPException(404, "Unknown platform")
    if db.scalar(select(ConnectedProfile).where(ConnectedProfile.user_id == user.id, ConnectedProfile.platform == body.platform, ConnectedProfile.handle == body.handle)):
        raise HTTPException(409, "Already linked")
    level = "link_only"
    if "submissions" in info.capabilities and info.adapter:
        try:  # verify the handle exists on the real platform before claiming anything
            adapters.ADAPTERS[body.platform]().validate_profile(body.handle)
            level = "public_api"
        except FetchError as e:
            raise HTTPException(422 if e.status in (400, 404) or "not found" in str(e) else 502, str(e)) from None
    p = ConnectedProfile(user_id=user.id, platform=body.platform, handle=body.handle, data_level=level)
    db.add(p); db.commit()
    return _prof(p)


def _own(db, user, pid) -> ConnectedProfile:
    p = db.get(ConnectedProfile, pid)
    if p is None or p.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    return p


@router.delete("/profiles/{pid}", status_code=204)
def unlink(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, pid)); db.commit()


@router.post("/profiles/{pid}/sync", status_code=202)
def sync(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _own(db, user, pid)
    if "submissions" not in BY_SLUG[p.platform].capabilities:
        raise HTTPException(422, f"{BY_SLUG[p.platform].name} has no verified sync capability. Use manual import instead.")
    j = ingest.enqueue(db, "profile_sync", p.platform, user.id, p.id)
    return {"job_id": j.id, "status": j.status}


@router.get("/sync-jobs")
def jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SyncJob).where(SyncJob.user_id == user.id).order_by(SyncJob.id.desc()).limit(30))
    return [{"id": j.id, "platform": j.platform, "kind": j.kind, "status": j.status, "attempts": j.attempts, "error": j.error,
             "stats": j.stats, "finished_at": j.finished_at} for j in rows]


@router.post("/profiles/{pid}/import")
async def manual_import(pid: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _own(db, user, pid)
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "File too large (2 MB max)")
    fmt = "json" if (file.filename or "").lower().endswith(".json") else "csv"
    try:
        rows, errors = adapters.parse_manual_import(p.platform, raw.decode("utf-8-sig"), fmt)
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(422, f"Could not parse file: {e}") from None
    stats = ingest.store_submissions(db, p, rows)
    if p.data_level == "link_only":
        p.data_level = "user_imported"
    ingest.refresh_progress_from_submissions(db, user.id)
    from app.services.recommender import rebuild_mastery
    rebuild_mastery(db, user.id)
    return {**stats, "rejected_rows": errors[:50], "rejected_count": len(errors), "label": "USER_IMPORTED (not verified by the platform)"}


@router.get("/contests")
def contests(platform: str | None = None, include_past_days: int = Query(0, ge=0, le=365), limit: int = Query(100, le=500),
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    since = datetime.now(UTC) - timedelta(days=include_past_days)
    q = select(Contest).where(Contest.start_time >= since).order_by(Contest.start_time).limit(limit)
    if platform:
        q = q.where(Contest.platform == platform)
    last = {r[0]: r[1] for r in db.execute(select(Contest.platform, func.max(Contest.synced_at)).group_by(Contest.platform))}
    return {"items": [{"id": c.id, "platform": c.platform, "name": c.name, "start_time": c.start_time, "duration_seconds": c.duration_seconds,
                       "url": c.url, "rated": c.rated, "source": c.source, "synced_at": c.synced_at} for c in db.scalars(q)],
            "last_synced": last, "note": "Only contests returned by a platform's own source are shown. Empty means not synced yet."}


# ------------------------------------------------------------- admin
@router.post("/admin/sync/{kind}/{platform}", status_code=202)
def admin_enqueue(kind: str, platform: str, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if kind not in ("contests", "problems") or platform not in BY_SLUG or not BY_SLUG[platform].adapter:
        raise HTTPException(422, "Unsupported kind/platform")
    return {"job_id": ingest.enqueue(db, kind, platform).id}


@router.post("/admin/jobs/run")
def admin_run(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {"ran": ingest.run_due_jobs(db)}


@router.post("/admin/sheets/import/{source}")
def admin_import_sheet(source: str, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    try:
        if source == "neetcode":
            specs = neetcode.build_specs(neetcode.fetch())
        elif source in takeuforward.SHEETS:
            specs = [takeuforward.build_spec(takeuforward.fetch_html(source), source)]
        else:
            raise HTTPException(404, "Unknown or non-importable source. See GET /sheet-sources")
    except FetchError as e:
        raise HTTPException(502, str(e)) from None
    return [sheet_import.import_sheet_spec(db, s) for s in specs]


# ------------------------------------------------------------- unified problem explorer
@router.get("/explorer")
def explorer(platform: str | None = None, sheet_id: int | None = None, tag: str | None = None, min_rating: int | None = None,
             max_rating: int | None = None, difficulty: str | None = None, solved: bool | None = None,
             q: str | None = Query(None, max_length=100), limit: int = Query(50, le=200), offset: int = 0,
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Problem)
    if platform: stmt = stmt.where(Problem.platform == platform)
    if min_rating is not None: stmt = stmt.where(Problem.rating >= min_rating)
    if max_rating is not None: stmt = stmt.where(Problem.rating <= max_rating)
    if difficulty: stmt = stmt.where(Problem.source_difficulty.ilike(difficulty))
    if q: stmt = stmt.where(Problem.name.ilike(f"%{q}%"))
    if sheet_id is not None:
        stmt = stmt.where(Problem.id.in_(select(SheetItem.problem_id).where(SheetItem.sheet_id == sheet_id)))
    solved_sq = select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True))
    if solved is True: stmt = stmt.where(Problem.id.in_(solved_sq))
    if solved is False: stmt = stmt.where(Problem.id.not_in(solved_sq))
    if tag:  # exact quoted match on the JSON text; a normalised problem_tags table is the scale-up path
        stmt = stmt.where(cast(Problem.tags, String).like(f'%"{tag.replace(chr(34), "")}"%'))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Problem.rating.is_(None), Problem.rating, Problem.id).limit(limit).offset(offset)).all()
    ids = [p.id for p in rows]
    done = set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True), ProblemStatus.problem_id.in_(ids)))) if ids else set()
    memb: dict[int, list[str]] = {}
    for pid, title in db.execute(select(SheetItem.problem_id, Sheet.title).join(Sheet, Sheet.id == SheetItem.sheet_id)
                                 .where(SheetItem.problem_id.in_(ids), or_(Sheet.owner_id.is_(None), Sheet.owner_id == user.id))):
        memb.setdefault(pid, []).append(title)
    platforms_ = {r[0]: r[1] for r in db.execute(select(Problem.platform, func.count()).group_by(Problem.platform))}
    return {"total": total, "platform_counts": platforms_, "items": [
        {"id": p.id, "platform": p.platform, "external_id": p.external_id, "name": p.name, "url": p.canonical_url or p.url,
         "rating": p.rating, "source_difficulty": p.source_difficulty, "tags": p.tags, "solved": p.id in done,
         "sheets": memb.get(p.id, [])} for p in rows]}


@router.get("/admin/data-quality")
def data_quality(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    from app.services.quality import build_report
    return build_report(db)
