"""Mistake notebook + revision centre logic. Diagnostics are deterministic from verdict mixes; the student's own notes are kept verbatim."""
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem
from app.models.daily import MistakeNote, ReviewItem, ReviewLog
from app.models.integrations import Submission
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID

BOX_DAYS = [1, 3, 7, 21, 60]
CAUSES = ("logic", "edge-case", "complexity", "implementation", "concept", "careless")
HINTS = {"TLE": ("efficiency", "Time limit exceeded: re-read the constraints and compare your complexity with n. Look for a repeated scan that a prefix sum, hash map or sort would remove."),
         "WA": ("logic", "Wrong answer: test tiny inputs against a brute force, then edge cases (n=1, all equal, max values, negatives). Re-derive the invariant instead of patching."),
         "RE": ("bounds", "Runtime error: check array bounds, division by zero, recursion depth and integer overflow."),
         "MLE": ("memory", "Memory limit: reduce the state (rolling DP rows, bitsets) or avoid storing every intermediate."),
         "CE": ("syntax", "Compile error: language/version issue or syntax; compile locally with warnings on.")}


def _aw(d):
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def notebook(db: Session, user_id: int, limit: int = 40) -> dict:
    rows = db.execute(select(Submission.problem_id, Submission.verdict, Submission.submitted_at).where(Submission.user_id == user_id, Submission.problem_id.is_not(None))
                      .order_by(Submission.submitted_at)).all()
    by: dict[int, dict] = defaultdict(lambda: {"fails": Counter(), "ac_at": None, "first": None, "last": None, "attempts": 0, "fails_before_ac": 0})
    for pid, v, at in rows:
        at = _aw(at); e = by[pid]
        e["attempts"] += 1; e["first"] = e["first"] or at; e["last"] = at
        if v == "AC":
            if e["ac_at"] is None:
                e["ac_at"], e["fails_before_ac"] = at, sum(e["fails"].values())
        elif e["ac_at"] is None:
            e["fails"][v] += 1
    notes = {n.problem_id: n for n in db.scalars(select(MistakeNote).where(MistakeNote.user_id == user_id))}
    cand = [pid for pid, e in by.items() if sum(e["fails"].values()) >= 2 or (e["ac_at"] and e["fails_before_ac"] >= 2) or pid in notes]
    probs = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(cand[:2000])))} if cand else {}
    pmap = mastery.problem_patterns(db)
    items = []
    pat_fail: Counter = Counter()
    verdict_total: Counter = Counter()
    for pid in cand:
        p, e = probs.get(pid), by[pid]
        if p is None:
            continue
        nf = sum(e["fails"].values()) if e["ac_at"] is None else e["fails_before_ac"]
        dom = (e["fails"].most_common(1)[0][0] if e["fails"] else None)
        verdict_total.update(e["fails"])
        for pt in pmap.get(pid, []):
            pat_fail[pt] += nf
        n = notes.get(pid)
        items.append({"problem": {"id": p.id, "name": p.name, "platform": p.platform, "url": p.canonical_url or p.url, "rating": p.rating, "tags": p.tags}, "status": "recovered" if e["ac_at"] else "open",
                      "failed_attempts": nf, "verdicts": dict(e["fails"]), "last_attempt": e["last"], "patterns": [BY_ID[x].name for x in pmap.get(pid, []) if x in BY_ID][:3],
                      "diagnosis": HINTS.get(dom, ("", ""))[1] if dom else None, "diagnosis_kind": HINTS.get(dom, ("", ""))[0] if dom else None,
                      "note": n.note if n else "", "cause": n.cause if n else None})
    items.sort(key=lambda x: (x["status"] != "open", -x["failed_attempts"]))
    top_pat = [{"pattern": k, "name": BY_ID[k].name, "failed_attempts": v} for k, v in pat_fail.most_common(5) if k in BY_ID]
    return {"items": items[:limit], "total": len(items), "recurring_patterns": top_pat,
            "verdict_mix": dict(verdict_total.most_common()), "note": "Failures are counted before the first accepted submission. Diagnoses are generic hints from the verdict mix, not a judgement of your code."}


def save_note(db: Session, user_id: int, problem_id: int, note: str, cause: str | None) -> MistakeNote:
    if cause is not None and cause not in CAUSES:
        raise ValueError(f"cause must be one of {CAUSES}")
    n = db.scalar(select(MistakeNote).where(MistakeNote.user_id == user_id, MistakeNote.problem_id == problem_id))
    if n is None:
        n = MistakeNote(user_id=user_id, problem_id=problem_id); db.add(n)
    n.note, n.cause = note[:2000], cause
    db.commit()
    return n


def enroll_recovered(db: Session, user_id: int, now: datetime | None = None) -> int:
    """Problems solved only after 2+ failures are exactly the ones worth reviewing: schedule them (box 0) if not already scheduled."""
    now = now or datetime.now(UTC)
    nb = notebook(db, user_id, limit=500)
    have = set(db.scalars(select(ReviewItem.problem_id).where(ReviewItem.user_id == user_id)))
    n = 0
    for it in nb["items"]:
        if it["status"] == "recovered" and it["failed_attempts"] >= 2 and it["problem"]["id"] not in have:
            db.add(ReviewItem(user_id=user_id, problem_id=it["problem"]["id"], due_at=now + timedelta(days=BOX_DAYS[1]), box=0, last_result="struggled")); n += 1
    db.commit()
    return n


def review(db: Session, user_id: int, problem_id: int, result: str, now: datetime | None = None) -> ReviewItem:
    if result not in ("good", "again"):
        raise ValueError("result must be 'good' or 'again'")
    now = now or datetime.now(UTC)
    rv = db.scalar(select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.problem_id == problem_id))
    if rv is None:
        raise LookupError("This problem is not in your revision schedule")
    due = _aw(rv.due_at)
    rv.box = min(rv.box + 1, len(BOX_DAYS) - 1) if result == "good" else 0
    rv.due_at, rv.last_result = now + timedelta(days=BOX_DAYS[rv.box]), result
    db.add(ReviewLog(user_id=user_id, problem_id=problem_id, result=result, was_due=due <= now, at=now))
    db.commit()
    return rv


def overview(db: Session, user_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    items = db.scalars(select(ReviewItem).where(ReviewItem.user_id == user_id).order_by(ReviewItem.due_at)).all()
    probs = {p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_([i.problem_id for i in items])))} if items else {}
    row = lambda r: {"problem": {"id": r.problem_id, "name": probs[r.problem_id].name, "url": probs[r.problem_id].canonical_url or probs[r.problem_id].url, "platform": probs[r.problem_id].platform,
                                 "rating": probs[r.problem_id].rating}, "due_at": r.due_at, "box": r.box, "last_result": r.last_result}
    due = [row(r) for r in items if _aw(r.due_at) <= now and r.problem_id in probs]
    soon = [row(r) for r in items if now < _aw(r.due_at) <= now + timedelta(days=7) and r.problem_id in probs]
    logs = db.scalars(select(ReviewLog).where(ReviewLog.user_id == user_id, ReviewLog.at >= now - timedelta(days=90))).all()
    due_logs = [l for l in logs if l.was_due]
    overdue_days = [max(0, (now - _aw(r.due_at)).days) for r in items if _aw(r.due_at) <= now]
    return {"due": due, "upcoming_7d": soon, "total_scheduled": len(items), "boxes": dict(Counter(r.box for r in items)), "schedule_days": BOX_DAYS,
            "consistency": {"reviews_90d": len(logs), "good_rate": round(sum(l.result == "good" for l in logs) / len(logs), 3) if logs else None,
                            "on_time_rate": round(len(due_logs) / len(logs), 3) if logs else None, "avg_days_overdue_now": round(sum(overdue_days) / len(overdue_days), 1) if overdue_days else 0,
                            "note": "on_time = the review was due when you did it. 'again' resets a problem to a 1-day interval."}}
