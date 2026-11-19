from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.api.mentor import get_router
from app.core.db import get_db
from app.llm.router import Router
from app.models.ai import ProblemPatternLabel
from app.models.catalog import Problem
from app.models.user import User
from app.patterns import labeling
from app.patterns.mapping import observable_patterns
from app.patterns.mastery import bump_catalog
from app.patterns.taxonomy import BY_ID, PATTERNS

router = APIRouter(tags=["labels"])
REVIEWER = require_role("moderator", "admin")


@router.get("/labels/queue")
def queue(status: str = "proposed", source: str | None = None, pattern: str | None = None, limit: int = Query(20, le=100), user: User = Depends(REVIEWER), db: Session = Depends(get_db)):
    q = select(ProblemPatternLabel, Problem).join(Problem, Problem.id == ProblemPatternLabel.problem_id).where(ProblemPatternLabel.status == status)
    if source: q = q.where(ProblemPatternLabel.source == source)
    if pattern: q = q.where(ProblemPatternLabel.pattern_id == pattern)
    rows = db.execute(q.order_by(ProblemPatternLabel.confidence.desc(), ProblemPatternLabel.id).limit(limit)).all()
    return [{"id": l.id, "pattern": l.pattern_id, "pattern_name": BY_ID[l.pattern_id].name if l.pattern_id in BY_ID else l.pattern_id, "source": l.source, "confidence": l.confidence, "reason": l.reason,
             "problem": {"id": p.id, "name": p.name, "platform": p.platform, "rating": p.rating, "tags": p.tags, "url": p.canonical_url or p.url}} for l, p in rows]


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    note: str = Field("", max_length=300)


@router.post("/labels/{lid}/review")
def review(lid: int, body: ReviewIn, user: User = Depends(REVIEWER), db: Session = Depends(get_db)):
    l = db.get(ProblemPatternLabel, lid)
    if l is None:
        raise HTTPException(404, "Label not found")
    l.status = "accepted" if body.decision == "accept" else "rejected"
    l.reviewer_id, l.note, l.reviewed_at = user.id, body.note, datetime.now(UTC)
    if l.status == "accepted" and l.source != "human":
        pass  # source stays 'rule'/'llm' so we can measure proposer precision from reviews
    db.commit()
    bump_catalog()
    return {"id": l.id, "status": l.status}


class AddIn(BaseModel):
    problem_id: int
    pattern_id: str
    note: str = Field("", max_length=300)


@router.post("/labels", status_code=201)
def add_human(body: AddIn, user: User = Depends(REVIEWER), db: Session = Depends(get_db)):
    if body.pattern_id not in BY_ID or BY_ID[body.pattern_id].kind == "category":
        raise HTTPException(422, "Unknown pattern")
    if db.get(Problem, body.problem_id) is None:
        raise HTTPException(404, "Problem not found")
    l = db.scalar(select(ProblemPatternLabel).where(ProblemPatternLabel.problem_id == body.problem_id, ProblemPatternLabel.pattern_id == body.pattern_id))
    if l is None:
        l = ProblemPatternLabel(problem_id=body.problem_id, pattern_id=body.pattern_id, source="human", confidence=1.0); db.add(l)
    l.status, l.reviewer_id, l.note, l.reviewed_at = "accepted", user.id, body.note, datetime.now(UTC)
    db.commit(); bump_catalog()
    return {"id": l.id}


class ProposeIn(BaseModel):
    source: str = Field(pattern="^(rule|llm)$")
    platform: str | None = None
    limit: int = Field(5, ge=1, le=50)


@router.post("/admin/labels/propose")
def propose(body: ProposeIn, _: User = Depends(require_role("admin")), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    if body.source == "rule":
        return labeling.propose_rules(db, body.platform)
    if not r.active():
        raise HTTPException(503, "No LLM provider available for proposals")
    ids = [pid for (pid,) in db.execute(select(Problem.id).where(Problem.status == "active", Problem.platform == (body.platform or "codeforces"), Problem.rating.is_not(None))
                                        .where(~Problem.id.in_(select(ProblemPatternLabel.problem_id))).order_by(func.random()).limit(body.limit))]
    return labeling.propose_llm(db, r, ids)


@router.get("/labels/stats")
def stats(user: User = Depends(REVIEWER), db: Session = Depends(get_db)):
    by = {f"{s}/{st}": n for s, st, n in db.execute(select(ProblemPatternLabel.source, ProblemPatternLabel.status, func.count()).group_by(ProblemPatternLabel.source, ProblemPatternLabel.status))}
    reviewed = {s: {"accepted": 0, "rejected": 0} for s in ("rule", "llm")}
    for s, st, n in db.execute(select(ProblemPatternLabel.source, ProblemPatternLabel.status, func.count()).where(ProblemPatternLabel.status.in_(("accepted", "rejected")), ProblemPatternLabel.reviewer_id.is_not(None)).group_by(ProblemPatternLabel.source, ProblemPatternLabel.status)):
        if s in reviewed: reviewed[s][st] = n
    prec = {s: (round(v["accepted"] / (v["accepted"] + v["rejected"]), 3) if v["accepted"] + v["rejected"] >= 20 else None) for s, v in reviewed.items()}
    accepted_pats = set(db.scalars(select(ProblemPatternLabel.pattern_id).where(ProblemPatternLabel.status == "accepted").distinct()))
    non_cat = [p.id for p in PATTERNS if p.kind != "category"]
    base = observable_patterns()
    return {"by_source_status": by, "reviewed": reviewed, "proposer_precision_from_human_review": prec, "precision_note": "Shown only after >=20 human reviews per source.",
            "measurable_patterns": {"before_labels": len([p for p in non_cat if p in base]), "with_accepted_labels": len([p for p in non_cat if p in base or p in accepted_pats]), "total": len(non_cat)}}
