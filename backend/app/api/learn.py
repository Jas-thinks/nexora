from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models.catalog import Problem
from app.models.daily import DailyChallenge, ReviewItem
from app.models.user import User
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID, PATTERNS, REVIEW_STATUS, VERSION
from app.services import daily

router = APIRouter(tags=["learn"])


def _problem(p: Problem) -> dict:
    return {"id": p.id, "platform": p.platform, "name": p.name, "url": p.canonical_url or p.url, "rating": p.rating,
            "source_difficulty": p.source_difficulty, "tags": p.tags,
            "provenance": "Metadata and canonical link only. The statement lives on the original platform."}


def _hints(pattern_id: str | None) -> list[dict]:
    """Pattern-level hints from the taxonomy (not problem-specific). Levels 3-5 need the AI mentor (LLM key not configured)."""
    pat = BY_ID.get(pattern_id or "")
    if not pat:
        return []
    hs = [{"level": 1, "text": f"Think about the pattern: {pat.name}."}]
    if pat.clues:
        hs.append({"level": 2, "text": "Recognise it by: " + "; ".join(pat.clues) + "."})
    elif pat.prereq:
        hs.append({"level": 2, "text": "Make sure you are comfortable with: " + ", ".join(BY_ID[q].name for q in pat.prereq) + "."})
    hs.append({"level": 3, "text": None, "unavailable": "Problem-specific hints and explanations need the AI mentor, which is not configured (no LLM key)."})
    return hs


def _ch(db: Session, ch: DailyChallenge) -> dict:
    p = db.get(Problem, ch.problem_id)
    return {"id": ch.id, "day": ch.day, "mode": ch.mode, "status": ch.status, "swaps": ch.swaps, "problem": _problem(p),
            "pattern": ch.primary_pattern, "explanation": ch.explanation, "objective_scores": ch.objective_scores,
            "hints": _hints(ch.primary_pattern), "feedback": ch.feedback, "policy": ch.policy_version}


@router.get("/daily")
def get_daily(mode: str = "personalized", path: str | None = None, topic: str | None = None,
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return _ch(db, daily.generate(db, user.id, datetime.now(UTC).date(), mode, path, topic))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except LookupError as e:
        raise HTTPException(404, str(e)) from None


def _own(db, user, cid) -> DailyChallenge:
    ch = db.get(DailyChallenge, cid)
    if ch is None or ch.user_id != user.id:
        raise HTTPException(404, "Challenge not found")
    return ch


class CompleteIn(BaseModel):
    solved: bool
    hints_used: int = Field(0, ge=0, le=10)
    editorial_viewed: bool = False
    self_difficulty: int = Field(3, ge=1, le=5)
    understanding: int | None = Field(None, ge=1, le=5)
    minutes: int | None = Field(None, ge=0, le=1440)  # only stored if the student chooses to send it (consent)


@router.post("/daily/{cid}/complete")
def complete(cid: int, body: CompleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ch = _own(db, user, cid)
    if ch.status != "assigned":
        raise HTTPException(409, f"Challenge is already {ch.status}")
    return _ch(db, daily.complete(db, ch, **body.model_dump()))


class SwapIn(BaseModel):
    reason: str = Field("", max_length=200)


@router.post("/daily/{cid}/swap")
def swap(cid: int, body: SwapIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ch = _own(db, user, cid)
    try:
        return _ch(db, daily.swap(db, ch, body.reason))
    except PermissionError as e:
        raise HTTPException(409, str(e)) from None
    except LookupError as e:
        raise HTTPException(404, str(e)) from None


@router.get("/daily/history")
def history(limit: int = Query(30, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(DailyChallenge).where(DailyChallenge.user_id == user.id, DailyChallenge.status != "swapped")
                      .order_by(DailyChallenge.day.desc(), DailyChallenge.id.desc()).limit(limit)).all()
    done = sum(r.status == "completed" for r in rows)
    return {"items": [_ch(db, r) for r in rows], "completed": done, "total": len(rows)}


@router.get("/revision/due")
def revision_due(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    items = db.scalars(select(ReviewItem).where(ReviewItem.user_id == user.id).order_by(ReviewItem.due_at)).all()
    def aw(d): return d if d.tzinfo else d.replace(tzinfo=UTC)
    return {"due": [{"problem": _problem(db.get(Problem, r.problem_id)), "due_at": r.due_at, "box": r.box} for r in items if aw(r.due_at) <= now],
            "upcoming": len([r for r in items if aw(r.due_at) > now]), "schedule_days": daily.BOX_DAYS}


# ----------------------------------------------------------------------------- patterns
def _pat(p) -> dict:
    return {"id": p.id, "name": p.name, "kind": p.kind, "parent": p.parent, "aliases": p.aliases, "prerequisites": p.prereq,
            "related": p.related, "contrasts_with": p.contrasts, "extends": p.extends, "complexity": p.complexity, "clues": p.clues}


@router.get("/patterns")
def patterns(user: User = Depends(current_user)):
    return {"version": VERSION, "review_status": REVIEW_STATUS, "count": len(PATTERNS), "patterns": [_pat(p) for p in PATTERNS],
            "note": "Authored taxonomy, not yet human-reviewed. Relationships are explicit edges, not inferred."}


@router.get("/patterns/coverage")
def pattern_coverage(user: User = Depends(current_user), db: Session = Depends(get_db)):
    states = mastery.assess_cached(db, user.id)
    return {**mastery.coverage(states), "patterns": [
        {"id": s.pattern, "name": BY_ID[s.pattern].name, "parent": BY_ID[s.pattern].parent, "status": s.status, "score": s.score, "solved": s.solved,
         "attempted": s.attempted, "due_for_revision": s.due_for_revision, "missing_prereqs": s.missing_prereqs} for s in states.values()]}


@router.get("/patterns/{pid}")
def pattern_detail(pid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pat = BY_ID.get(pid)
    if pat is None:
        raise HTTPException(404, "Unknown pattern")
    states = mastery.assess_cached(db, user.id)
    pmap = mastery.problem_patterns(db)
    ids = [i for i, ps in pmap.items() if pid in ps]
    probs = list(db.scalars(select(Problem).where(Problem.id.in_(ids[:5000])))) if ids else []
    tiers: dict[int, list[Problem]] = {1: [], 2: [], 3: []}
    for p in sorted(probs, key=lambda x: (x.rating or 0, x.id)):
        if (t := mastery.tier(p)):
            tiers[t].append(p)
    st = states.get(pid)
    return {**_pat(pat), "children": [_pat(c) for c in PATTERNS if c.parent == pid],
            "leads_to": [q.id for q in PATTERNS if pid in q.prereq],
            "mastery": None if st is None else {"status": st.status, "score": st.score, "solved": st.solved, "attempted": st.attempted,
                                                 "accuracy": st.accuracy, "reasons": st.reasons, "missing_prereqs": st.missing_prereqs,
                                                 "due_for_revision": st.due_for_revision},
            "problems": {name: [_problem(p) for p in tiers[t][:6]] for t, name in ((1, "beginner"), (2, "intermediate"), (3, "advanced"))},
            "problem_count": len(ids),
            "learning_page": {"status": "outline", "note": "Full learning pages (intuition, templates, mistakes) are not written yet; this is metadata, relationships and real problems."}}
