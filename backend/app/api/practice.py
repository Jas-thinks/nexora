import json
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.models.catalog import Problem, ProblemStatus, Sheet, SheetItem, TopicMastery
from app.models.user import User
from app.services import codeforces, recommender, sheets

router = APIRouter(tags=["practice"])
STARTER = Path(__file__).resolve().parents[2] / "data" / "sheets" / "nexora_starter_800.json"


def _pdict(p: Problem) -> dict:
    return {"id": p.id, "name": p.name, "rating": p.rating, "tags": p.tags, "url": p.canonical_url or p.url, "external_id": p.external_id,
            "platform": p.platform, "source_difficulty": p.source_difficulty}


@router.post("/catalog/sync/codeforces")
def sync_codeforces(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    try:
        raw = codeforces.fetch_problemset()
    except (httpx.HTTPError, RuntimeError) as e:
        raise HTTPException(502, f"Codeforces sync failed: {e}") from None
    return codeforces.upsert_problems(db, codeforces.normalize(raw))


@router.get("/problems")
def list_problems(min_rating: int | None = None, max_rating: int | None = None, tag: str | None = None,
                  q: str | None = Query(None, max_length=100), limit: int = Query(50, le=200), offset: int = 0,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Problem).where(Problem.rating.is_not(None))
    if min_rating is not None: stmt = stmt.where(Problem.rating >= min_rating)
    if max_rating is not None: stmt = stmt.where(Problem.rating <= max_rating)
    if q: stmt = stmt.where(Problem.name.ilike(f"%{q}%"))
    rows = [p for p in db.scalars(stmt.order_by(Problem.rating, Problem.id)) if tag is None or tag in p.tags]
    solved = set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True))))
    return {"total": len(rows), "items": [{**_pdict(p), "solved": p.id in solved} for p in rows[offset:offset + limit]]}


class OutcomeIn(BaseModel):
    problem_id: int
    solved: bool


@router.post("/progress")
def report_outcome(body: OutcomeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Problem, body.problem_id)
    if p is None:
        raise HTTPException(404, "Problem not found")
    est, _ = recommender.estimate_rating_map(recommender.outcome_pairs(db, user.id))
    recommender.record_outcome(db, user.id, p, body.solved, est)
    new_est, conf = recommender.estimate_rating_map(recommender.outcome_pairs(db, user.id))
    return {"estimated_rating": new_est, "confidence": conf}


@router.get("/recommendations")
def recommendations(count: int = Query(8, ge=1, le=20), topic: str | None = None, target_rating: int | None = Query(None, ge=800, le=3500),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    return recommender.recommend(db, user.id, count=count, topic=topic, target_rating=target_rating)


@router.get("/mastery")
def mastery(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ms = db.scalars(select(TopicMastery).where(TopicMastery.user_id == user.id).order_by(TopicMastery.p_known)).all()
    solved = db.scalar(select(func.count()).select_from(ProblemStatus).where(ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True)))
    from app.patterns import mastery as _m
    est, conf = _m.estimate_cached(db, user.id)
    return {"solved": solved, "estimated_rating": est, "confidence": conf,
            "topics": [{"topic": m.topic, "mastery": round(m.p_known, 3), "attempts": m.attempts} for m in ms]}


class SheetItemIn(BaseModel):
    problem: str = Field(max_length=300)
    section: str = Field("", max_length=120)


class SheetIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    title: str = Field(min_length=1, max_length=200)
    source: str = Field("", max_length=300)
    description: str = Field("", max_length=1000)
    items: list[SheetItemIn] = Field(max_length=2000)


@router.post("/sheets/import", status_code=201)
def import_user_sheet(body: SheetIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return sheets.import_sheet(db, body.model_dump(), owner_id=user.id)


@router.post("/sheets/seed-starter")
def seed_starter(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return sheets.import_sheet(db, json.loads(STARTER.read_text()), owner_id=None)


@router.get("/sheets")
def list_sheets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for s in db.scalars(select(Sheet).where(or_(Sheet.owner_id.is_(None), Sheet.owner_id == user.id))):
        ids = list(db.scalars(select(SheetItem.problem_id).where(SheetItem.sheet_id == s.id)))
        done = db.scalar(select(func.count()).select_from(ProblemStatus).where(
            ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True), ProblemStatus.problem_id.in_(ids))) if ids else 0
        rep = s.import_report or {}
        out.append({"id": s.id, "slug": s.slug, "title": s.title, "source": s.source, "description": s.description,
                    "total": len(ids), "solved": done, "mine": s.owner_id == user.id, "source_url": s.source_url, "license": s.license,
                    "imported_at": s.imported_at, "by_platform": rep.get("by_platform", {}),
                    "skipped_no_problem_link": len(rep.get("skipped_no_problem_link", [])), "duplicates_in_source": len(rep.get("duplicates_in_sheet", []))})
    return out


@router.get("/sheets/{sheet_id}")
def get_sheet(sheet_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Sheet, sheet_id)
    if s is None or (s.owner_id not in (None, user.id)):
        raise HTTPException(404, "Sheet not found")  # same response for foreign private sheets
    solved = set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True))))
    rows = db.execute(select(SheetItem, Problem).join(Problem, Problem.id == SheetItem.problem_id)
                      .where(SheetItem.sheet_id == s.id).order_by(SheetItem.position)).all()
    return {"id": s.id, "title": s.title, "source": s.source, "description": s.description, "source_url": s.source_url,
            "license": s.license, "imported_at": s.imported_at, "import_report": s.import_report,
            "items": [{**_pdict(p), "section": it.section, "solved": p.id in solved} for it, p in rows]}
