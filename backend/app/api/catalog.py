from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.integrations.source_matrix import MATRIX, REFERENCES, VERIFIED_ON
from app.models.catalog import Problem, ProblemStatisticsSnapshot, ProblemStatus, Sheet, SheetItem
from app.models.integrations import Contest
from app.models.user import User
from app.patterns import mastery
from app.services import catalog_stats, ingest
from app.sources.sources import SOURCES

router = APIRouter(tags=["catalog"])


@router.get("/sources")
def sources(user: User = Depends(current_user), db: Session = Depends(get_db)):
    per, st = catalog_stats.per_platform(db), catalog_stats.sync_state(db)
    rows = []
    for m in MATRIX:
        enum = (st.get(m["slug"]) or {}).get("enumerate")
        rows.append({**m, "records": per.get(m["slug"]), "sync": enum, "unresolved_failures": (st.get(m["slug"]) or {}).get("unresolved_failures", 0),
                     "can_backfill": m["slug"] in SOURCES})
    return {"verified_on": VERIFIED_ON, "sources": rows, "totals": catalog_stats.totals(db),
            "references": [{"slug": s, "name": n, "url": u, "note": t} for s, n, u, t in REFERENCES],
            "note": "Coverage is reported against what each source itself says it lists ('discovered'). No source is claimed complete without that evidence."}


@router.post("/admin/backfill/{platform}", status_code=202)
def start_backfill(platform: str, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if platform not in SOURCES:
        raise HTTPException(422, f"No problem-source adapter for '{platform}'. See GET /sources for why.")
    return {"job_id": ingest.enqueue(db, "backfill", platform).id}


@router.get("/analytics/catalog")
def analytics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return catalog_stats.catalog_analytics(db)


@router.get("/problems/{pid}")
def problem_detail(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Problem, pid)
    if p is None:
        raise HTTPException(404, "Problem not found")
    contest = db.scalar(select(Contest).where(Contest.platform == p.platform, Contest.external_id == p.contest_ref)) if p.contest_ref else None
    snaps = db.scalars(select(ProblemStatisticsSnapshot).where(ProblemStatisticsSnapshot.problem_id == pid).order_by(ProblemStatisticsSnapshot.observed_at.desc()).limit(20)).all()
    sheets = db.execute(select(Sheet.title, SheetItem.section).join(SheetItem, SheetItem.sheet_id == Sheet.id).where(SheetItem.problem_id == pid)).all()
    st = db.scalar(select(ProblemStatus).where(ProblemStatus.user_id == user.id, ProblemStatus.problem_id == pid))
    pats = mastery.problem_patterns(db).get(pid, [])
    return {
        "id": p.id, "platform": p.platform, "external_id": p.external_id, "name": p.name, "url": p.canonical_url or p.url, "status": p.status,
        "difficulty": {"rating": p.rating, "source_label": p.source_difficulty, "note": "Each platform's own scale; not comparable across platforms."},
        "tags": p.tags, "patterns": pats, "contest": None if contest is None else {"id": contest.external_id, "name": contest.name, "start_time": contest.start_time, "url": contest.url},
        "contest_ref": p.contest_ref, "problem_index": p.problem_index, "limits": {"time_ms": p.time_limit_ms, "memory_kb": p.memory_limit_kb},
        "published_at": p.published_at,
        "statistics": {"solved_count": p.solved_count, "submission_count": p.submission_count,
                       "history": [{"observed_at": s.observed_at, "solved_count": s.solved_count, "submission_count": s.submission_count, "source": s.source} for s in snaps]},
        "provenance": {"source": p.source, "observed_at": p.observed_at, "raw_record_preserved": p.source_record is not None, "statement_access": p.statement_access,
                       "note": "Statement and editorial remain on the original platform; Nexora stores metadata and the canonical link."},
        "sheets": [{"title": t, "section": s} for t, s in sheets], "yours": None if st is None else {"solved": st.solved, "attempts": st.attempts, "provenance": st.provenance}}
