"""Catalog completeness and analytics computed from persisted data (SQL aggregates; nothing loaded wholesale except tag lists)."""
from collections import Counter

from sqlalchemy import Integer, String, case, cast, extract, func, select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, ProblemStatisticsSnapshot, Sheet, SheetItem, SyncCheckpoint, SyncFailure
from app.models.integrations import Contest

FIELDS = {
    "title": Problem.name != "", "difficulty": (Problem.rating.is_not(None)) | (Problem.source_difficulty.is_not(None)),
    "rating": Problem.rating.is_not(None), "topics": cast(Problem.tags, String) != "[]", "contest": Problem.contest_ref.is_not(None),
    "limits": Problem.time_limit_ms.is_not(None), "published": Problem.published_at.is_not(None), "statistics": Problem.solved_count.is_not(None),
    "provenance": Problem.source_record.is_not(None),
}


def per_platform(db: Session) -> dict[str, dict]:
    cols = [Problem.platform, func.count().label("total"),
            func.sum(case((Problem.status == "active", 1), else_=0)).label("active"),
            func.sum(case((Problem.status == "missing_upstream", 1), else_=0)).label("missing_upstream"),
            func.sum(case((Problem.status == "inaccessible", 1), else_=0)).label("inaccessible")]
    cols += [func.sum(case((cond, 1), else_=0)).label(f"f_{k}") for k, cond in FIELDS.items()]
    out = {}
    for r in db.execute(select(*cols).group_by(Problem.platform)):
        m = r._mapping
        total = m["total"]
        out[m["platform"]] = {"records": total, "active": int(m["active"] or 0), "missing_upstream": int(m["missing_upstream"] or 0),
                              "inaccessible": int(m["inaccessible"] or 0),
                              "completeness": {k: round(100 * int(m[f"f_{k}"] or 0) / total, 1) for k in FIELDS}}
    return out


def sync_state(db: Session) -> dict[str, dict]:
    st = {}
    for c in db.scalars(select(SyncCheckpoint)):
        st.setdefault(c.platform, {})[c.stage] = {"done": c.done, "discovered": c.discovered or None, "retrieved": c.retrieved,
                                                  "cursor": c.cursor, "started_at": c.started_at, "completed_at": c.completed_at, "updated_at": c.updated_at}
    fails = dict(db.execute(select(SyncFailure.platform, func.count()).where(SyncFailure.resolved.is_(False)).group_by(SyncFailure.platform)).all())
    for p, n in fails.items():
        st.setdefault(p, {})["unresolved_failures"] = n
    return st


def totals(db: Session) -> dict:
    c = lambda s: db.scalar(s) or 0
    return {"platform_records": c(select(func.count()).select_from(Problem)),
            "canonical_urls": c(select(func.count(func.distinct(Problem.canonical_url)))),
            "contests": c(select(func.count()).select_from(Contest)), "sheets": c(select(func.count()).select_from(Sheet)),
            "sheet_memberships": c(select(func.count()).select_from(SheetItem)),
            "statistics_snapshots": c(select(func.count()).select_from(ProblemStatisticsSnapshot)),
            "unresolved_failures": c(select(func.count()).select_from(SyncFailure).where(SyncFailure.resolved.is_(False))),
            "missing_upstream": c(select(func.count()).select_from(Problem).where(Problem.status == "missing_upstream")),
            "inaccessible": c(select(func.count()).select_from(Problem).where(Problem.status == "inaccessible")),
            "last_sync": db.scalar(select(func.max(SyncCheckpoint.completed_at)))}


def catalog_analytics(db: Session) -> dict:
    """Per-platform views only: scales are never mixed (CF rating vs AtCoder estimate vs LeetCode label)."""
    out: dict = {"note": "Difficulty is reported on each source's own scale; platforms are never ranked against each other on one axis."}
    out["problems_per_platform"] = dict(db.execute(select(Problem.platform, func.count()).group_by(Problem.platform)).all())
    band = (cast(Problem.rating / 100, Integer) * 100)
    out["codeforces_rating_distribution"] = {int(b): n for b, n in db.execute(select(band, func.count()).where(Problem.platform == "codeforces", Problem.rating.is_not(None))
                                                                              .group_by(band).order_by(band))}
    labels: Counter = Counter()
    for p, d in db.execute(select(Problem.platform, Problem.source_difficulty).where(Problem.source_difficulty.is_not(None), Problem.platform == "leetcode")):
        labels[f"{p}:{d}"] += 1  # grouped in Python: Postgres rejects GROUP BY on separately-parameterised expressions
    out["source_difficulty_labels"] = dict(labels)
    yr = extract("year", Problem.published_at)  # one expression object reused in SELECT and GROUP BY; portable across SQLite/Postgres
    per_year: dict[str, dict[str, int]] = {}
    for p, y, n in db.execute(select(Problem.platform, yr, func.count()).where(Problem.published_at.is_not(None)).group_by(Problem.platform, yr)):
        per_year.setdefault(p, {})[str(int(y))] = n
    out["published_per_year"] = per_year  # only platforms that expose a publication date
    cy = extract("year", Contest.start_time)
    cf_year = Counter()
    for y, n in db.execute(select(cy, func.count(Problem.id)).join(Contest, (Contest.platform == Problem.platform) & (Contest.external_id == Problem.contest_ref))
                           .where(Problem.platform == "codeforces").group_by(cy)):
        cf_year[str(int(y))] = n
    out["codeforces_problems_per_contest_year"] = dict(sorted(cf_year.items()))
    tags = Counter()
    for (t,) in db.execute(select(Problem.tags).where(cast(Problem.tags, String) != "[]")):
        tags.update(t)
    out["top_tags"] = tags.most_common(25)
    out["most_solved_by_platform"] = {p: [{"name": n, "solved_count": s} for n, s in db.execute(
        select(Problem.name, Problem.solved_count).where(Problem.platform == p, Problem.solved_count.is_not(None)).order_by(Problem.solved_count.desc()).limit(5))]
        for p in ("codeforces", "atcoder", "codechef", "cses", "projecteuler")}
    memb = select(SheetItem.problem_id, func.count().label("n")).group_by(SheetItem.problem_id).subquery()
    out["sheet_overlap"] = {"problems_on_2plus_sheets": db.scalar(select(func.count()).select_from(memb).where(memb.c.n >= 2)) or 0,
                            "problems_on_any_sheet": db.scalar(select(func.count()).select_from(memb)) or 0}
    return out
