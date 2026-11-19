"""Contest preparation and post-contest review. Deterministic; built from the student's own data. Codeforces-specific parts only when the data exists."""
import statistics
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem
from app.models.integrations import ConnectedProfile, Contest, RatingHistory, Submission
from app.models.daily import ReviewItem
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID
from app.services import daily


def _aw(d):
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def prep(db: Session, user_id: int, contest_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    c = db.get(Contest, contest_id)
    if c is None:
        raise LookupError("Contest not found")
    prof = db.scalar(select(ConnectedProfile).where(ConnectedProfile.user_id == user_id, ConnectedProfile.platform == c.platform))
    out = {"contest": {"id": c.id, "name": c.name, "platform": c.platform, "start_time": c.start_time, "duration_seconds": c.duration_seconds, "url": c.url, "rated": c.rated},
           "starts_in_hours": None if c.start_time is None else round((_aw(c.start_time) - now).total_seconds() / 3600, 1), "linked_profile": prof is not None}
    states = mastery.assess_cached(db, user_id)
    est, conf = mastery.estimate_cached(db, user_id)
    rh = list(db.scalars(select(RatingHistory).where(RatingHistory.user_id == user_id, RatingHistory.platform == c.platform).order_by(RatingHistory.at)))
    deltas = [r.new_rating - r.old_rating for r in rh[-8:] if r.new_rating is not None and r.old_rating]
    out["recent_form"] = {"contests": len(rh), "current_rating": rh[-1].new_rating if rh else None, "last8_change": sum(deltas) if deltas else None,
                          "volatility": round(statistics.pstdev(deltas), 1) if len(deltas) >= 3 else None} if rh else None
    weak = [s for s in sorted(states.values(), key=lambda s: s.score) if s.status in ("weak", "learning") and not s.missing_prereqs][:3]
    due = len(db.scalars(select(ReviewItem.id).where(ReviewItem.user_id == user_id, ReviewItem.due_at <= now)).all())
    out["focus"] = {"patterns_to_revise": [{"id": s.pattern, "name": BY_ID[s.pattern].name, "status": s.status, "score": s.score} for s in weak], "reviews_due": due, "estimated_rating": est, "rating_confidence": conf}
    pool = []
    if c.platform == "codeforces":  # personalised warm-up from the existing ranker (cp mode), unsolved, near the student's level
        ctx = daily.build_ctx(db, user_id, now.date(), "cp", None, None)
        cand = daily._pool(db, "cp", ctx.lo, ctx.hi, ctx.user_tier, ctx.sheet_ids)
        cand = [p for p in cand if p.id not in ctx.solved_ids]
        ranked = daily.rank(ctx, cand)[:3]
        pool = [{"id": p.id, "name": p.name, "rating": p.rating, "url": p.canonical_url or p.url, "pattern": BY_ID[prim].name, "why": f"Targets {BY_ID[prim].name} (your status: {ctx.states[prim].status})"} for _, p, prim, _ in ranked]
    out["warmup_problems"] = pool
    dur_h = (c.duration_seconds or 7200) / 3600
    out["strategy"] = [f"Contest length ≈ {dur_h:g} h: aim to finish the first two problems in the first {max(20, int(dur_h * 60 * 0.25))} minutes.",
                       "Read all problems once before committing; submit only after testing small and edge cases (n=1, equal values, max constraints).",
                       "If stuck > 25 minutes on one problem, move on and return with a fresh view.", "Keep penalties in mind: a wrong submission costs time on most rulesets."]
    out["checklist"] = ["Templates and fast I/O ready", "Linked platform handle verified" if prof else "Link your handle (Platforms page) for personalised prep", "Sleep and water", f"{due} review(s) due: clear them first" if due else "No reviews due"]
    out["note"] = "Generic strategy plus advice derived from your own history; no outcome is predicted."
    return out


def review(db: Session, user_id: int, contest_id: int) -> dict:
    c = db.get(Contest, contest_id)
    if c is None:
        raise LookupError("Contest not found")
    rh = db.scalar(select(RatingHistory).where(RatingHistory.user_id == user_id, RatingHistory.platform == c.platform, RatingHistory.contest_ref == c.external_id))
    subs = db.execute(select(Submission.problem_ref, Submission.problem_id, Submission.verdict, Submission.submitted_at, Submission.in_contest)
                      .where(Submission.user_id == user_id, Submission.platform == c.platform)).all()
    pref = c.external_id if c.platform == "codeforces" else None
    mine = [s for s in subs if pref and s[0].startswith(pref) and s[0][len(pref):][:1].isalpha() and s[0][len(pref):].isalnum() and s[4] is True]  # index starts with a letter: '5001A' is NOT contest 500
    if rh is None and not mine:
        return {"contest": {"id": c.id, "name": c.name}, "available": False, "message": "No participation data for this contest. Rating history and in-contest submissions are only available for synced Codeforces contests."}
    per: dict[str, dict] = {}
    for ref, pid, v, at, _ in sorted(mine, key=lambda s: s[3]):
        e = per.setdefault(ref, {"problem_ref": ref, "problem_id": pid, "attempts": 0, "solved": False, "verdicts": []})
        e["attempts"] += 1; e["verdicts"].append(v); e["solved"] = e["solved"] or v == "AC"
    pmap = mastery.problem_patterns(db)
    names = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_([e["problem_id"] for e in per.values() if e["problem_id"]])))} if per else {}
    up = []
    for e in per.values():
        p = names.get(e["problem_id"])
        e["name"] = p.name if p else None
        e["patterns"] = [BY_ID[x].name for x in pmap.get(e["problem_id"], []) if x in BY_ID][:3] if e["problem_id"] else []
        if not e["solved"]:
            up.append({"problem_id": e["problem_id"], "name": e["name"], "attempts": e["attempts"], "patterns": e["patterns"], "url": (p.canonical_url or p.url) if p else None})
    return {"contest": {"id": c.id, "name": c.name, "platform": c.platform}, "available": True,
            "rating": None if rh is None else {"old": rh.old_rating, "new": rh.new_rating, "change": None if rh.new_rating is None or rh.old_rating is None else rh.new_rating - rh.old_rating, "rank": rh.rank, "performance": rh.performance},
            "problems": list(per.values()), "solved": sum(e["solved"] for e in per.values()), "attempted": len(per), "upsolve": up,
            "note": "Only submissions flagged as made during the contest are included. Time-to-solve is not shown because per-problem timing isn't reliably available."}
