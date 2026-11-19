from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core import cache
from app.core.db import get_db
from app.models.ai import Design
from app.models.catalog import Problem, ProblemStatus
from app.models.resources import Company, CompanyProblem, DesignQuestion
from app.models.user import User
from app.resources import design_questions
from app.resources.company_lists import SOURCE
from app.resources.tiers import TIER_LABELS

router = APIRouter(tags=["resources"])
ATTRIBUTION = {"source": SOURCE, "url": "https://github.com/liquidslr/leetcode-company-wise-problems",
               "disclaimer": "Company lists are reported by candidates and aggregated by a third party. They are not official, can be stale or wrong, and say nothing about what you will be asked. Tiers are Nexora's own grouping, not salary data."}
DIFFS = ("Easy", "Medium", "Hard")


def _solved_subq(user: User):
    return select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user.id, ProblemStatus.solved.is_(True))


@router.get("/resources/overview")
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    solved_ids = _solved_subq(user)
    def _global():
        rows = db.execute(select(Company.tier, func.count(Company.id), func.sum(Company.problem_count)).group_by(Company.tier)).all()
        tiers = [{"id": t, "label": TIER_LABELS[t], "companies": n, "problem_links": int(s or 0)} for t, n, s in rows if t in TIER_LABELS]
        order = list(TIER_LABELS)
        tiers.sort(key=lambda x: order.index(x["id"]))
        return {"tiers": tiers, "distinct": db.scalar(select(func.count(func.distinct(CompanyProblem.problem_id)))), "seeded": db.scalar(select(func.count(DesignQuestion.id)))}
    g = cache.cached("res:overview", 300, _global)  # identical for every user; the per-user 'solved' count below is not cached
    tiers, distinct, seeded = g["tiers"], g["distinct"], g["seeded"]
    solved = db.scalar(select(func.count(func.distinct(CompanyProblem.problem_id))).where(CompanyProblem.problem_id.in_(solved_ids)))
    return {"tiers": tiers, "tier_labels": TIER_LABELS, "distinct_problems": distinct, "you_solved": solved, "design_questions": seeded, "attribution": ATTRIBUTION,
            "empty": not tiers}


@router.get("/resources/companies")
def companies(tier: str | None = None, q: str | None = Query(None, max_length=60), limit: int = Query(60, ge=1, le=200), offset: int = Query(0, ge=0),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    def _page():
        base = select(Company)
        if tier:
            base = base.where(Company.tier == tier)
        if q:
            base = base.where(func.lower(Company.name).contains(q.strip().lower()))
        total = db.scalar(select(func.count()).select_from(base.subquery()))
        cos = db.scalars(base.order_by(Company.problem_count.desc(), Company.name).limit(limit).offset(offset)).all()
        return {"total": total, "rows": [{"id": c.id, "slug": c.slug, "name": c.name, "tier": c.tier, "domain": c.domain, "problems": c.problem_count} for c in cos]}
    page = cache.cached(f"res:companies:{tier}:{(q or '').strip().lower()}:{limit}:{offset}", 300, _page)
    ids = [r["id"] for r in page["rows"]]
    solved = dict(db.execute(select(CompanyProblem.company_id, func.count()).where(CompanyProblem.company_id.in_(ids), CompanyProblem.problem_id.in_(_solved_subq(user))).group_by(CompanyProblem.company_id)).all()) if ids else {}
    return {"total": page["total"], "items": [{"slug": r["slug"], "name": r["name"], "tier": r["tier"], "domain": r["domain"], "problems": r["problems"], "solved": solved.get(r["id"], 0)} for r in page["rows"]]}


def _co(db: Session, slug: str) -> Company:
    c = db.scalar(select(Company).where(Company.slug == slug))
    if c is None:
        raise HTTPException(404, "Company not found")
    return c


@router.get("/resources/companies/{slug}")
def company(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _co(db, slug)
    solved_ids = _solved_subq(user)
    split = {d: [0, 0] for d in DIFFS}
    for d, n, s in db.execute(select(Problem.source_difficulty, func.count(), func.sum(case((Problem.id.in_(solved_ids), 1), else_=0)))
                              .join(CompanyProblem, CompanyProblem.problem_id == Problem.id).where(CompanyProblem.company_id == c.id).group_by(Problem.source_difficulty)):
        if d in split:
            split[d] = [n, int(s or 0)]
    topics: dict[str, int] = {}
    for (tags,) in db.execute(select(Problem.tags).join(CompanyProblem, CompanyProblem.problem_id == Problem.id).where(CompanyProblem.company_id == c.id)):
        for t in tags or []:
            topics[t] = topics.get(t, 0) + 1
    top = sorted(topics.items(), key=lambda kv: -kv[1])[:14]
    rec = db.scalar(select(func.count()).select_from(CompanyProblem).where(CompanyProblem.company_id == c.id, CompanyProblem.recent.is_(True)))
    sd = [{"slug": q.slug, "title": q.title, "level": q.level} for q in db.scalars(select(DesignQuestion).where(DesignQuestion.kind == "hld").order_by(DesignQuestion.id))
          if c.domain and c.domain in (q.domains or [])][:6]
    return {"slug": c.slug, "name": c.name, "tier": c.tier, "tier_label": TIER_LABELS[c.tier], "domain": c.domain, "problems": c.problem_count, "recent_problems": rec,
            "difficulty": {d: {"total": v[0], "solved": v[1]} for d, v in split.items()}, "topics": [{"topic": t, "count": n} for t, n in top],
            "suggested_design": sd, "suggested_design_note": "Suggested by Nexora from the company's domain. It is not reported interview data." if sd else None, "attribution": ATTRIBUTION}


@router.get("/resources/companies/{slug}/problems")
def company_problems(slug: str, difficulty: str | None = None, topic: str | None = Query(None, max_length=40), recent: bool = False, unsolved: bool = False,
                     sort: str = Query("frequency", pattern="^(frequency|difficulty|name)$"), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _co(db, slug)
    solved_ids = _solved_subq(user)
    q = select(Problem, CompanyProblem.frequency, CompanyProblem.recent, Problem.id.in_(solved_ids).label("solved")).join(CompanyProblem, CompanyProblem.problem_id == Problem.id).where(CompanyProblem.company_id == c.id)
    if difficulty in DIFFS:
        q = q.where(Problem.source_difficulty == difficulty)
    if recent:
        q = q.where(CompanyProblem.recent.is_(True))
    if unsolved:
        q = q.where(~Problem.id.in_(solved_ids))
    if topic:
        q = q.where(func.lower(cast(Problem.tags, String)).contains(f'"{topic.lower()}"'))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    order = {"frequency": CompanyProblem.frequency.desc(), "difficulty": case((Problem.source_difficulty == "Easy", 0), (Problem.source_difficulty == "Medium", 1), else_=2), "name": Problem.name}[sort]
    rows = db.execute(q.order_by(order, Problem.name).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": p.id, "name": p.name, "url": p.url, "difficulty": p.source_difficulty, "topics": p.tags, "frequency": round(f, 1), "recent": r, "solved": bool(s)} for p, f, r, s in rows]}


@router.get("/resources/must-do")
def must_do(tier: str = Query("service"), difficulty: str | None = None, limit: int = Query(50, ge=1, le=200), unsolved: bool = False,
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Problems reported by the MOST companies in a tier (ties broken by mean reported frequency): the best-value list for that group."""
    if tier not in TIER_LABELS:
        raise HTTPException(422, "unknown tier")
    solved_ids = _solved_subq(user)
    q = (select(Problem, func.count(CompanyProblem.id).label("n"), func.avg(CompanyProblem.frequency).label("avg"), Problem.id.in_(solved_ids).label("solved"))
         .join(CompanyProblem, CompanyProblem.problem_id == Problem.id).join(Company, Company.id == CompanyProblem.company_id).where(Company.tier == tier).group_by(Problem.id))
    if difficulty in DIFFS:
        q = q.where(Problem.source_difficulty == difficulty)
    if unsolved:
        q = q.where(~Problem.id.in_(solved_ids))
    rows = db.execute(q.order_by(func.count(CompanyProblem.id).desc(), func.avg(CompanyProblem.frequency).desc(), Problem.name).limit(limit)).all()
    return {"tier": tier, "label": TIER_LABELS[tier], "items": [{"id": p.id, "name": p.name, "url": p.url, "difficulty": p.source_difficulty, "topics": p.tags, "companies": n, "avg_frequency": round(float(a or 0), 1), "solved": bool(s)}
                                                                 for p, n, a, s in rows], "attribution": ATTRIBUTION}


def _ensure_questions(db: Session) -> None:
    if not db.scalar(select(func.count(DesignQuestion.id))):
        design_questions.seed(db)


def _dq(q: DesignQuestion, status: dict) -> dict:
    return {"slug": q.slug, "title": q.title, "prompt": q.prompt, "level": q.level, "category": q.category, "kind": q.kind, "concepts": q.concepts, "domains": q.domains, "status": status.get(q.slug)}


@router.get("/resources/system-design")
def system_design(level: str | None = None, category: str | None = None, kind: str | None = None, domain: str | None = None, q: str | None = Query(None, max_length=60),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    _ensure_questions(db)
    st = {d.question: ("reviewed" if (d.doc or {}).get("reviewed") else "started") for d in db.scalars(select(Design).where(Design.user_id == user.id, Design.question.is_not(None)))}
    qs = db.scalars(select(DesignQuestion).order_by(DesignQuestion.id)).all()
    out = [x for x in qs if (not level or x.level == level) and (not category or x.category == category) and (not kind or x.kind == kind) and (not domain or domain in (x.domains or []))
           and (not q or q.lower() in (x.title + " " + " ".join(x.concepts or [])).lower())]
    return {"total": len(out), "items": [_dq(x, st) for x in out], "categories": sorted({x.category for x in qs}), "levels": ["entry", "mid", "senior"],
            "note": "Levels are Nexora's judgement of typical seniority, and 'domains' is a relevance hint, not reported interview data. Company-specific system-design reports are not available as open data, so none are claimed."}


@router.post("/resources/admin/seed-design")
def seed_design(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    n = design_questions.seed(db)
    cache.invalidate("res:")
    return {"added": n}
