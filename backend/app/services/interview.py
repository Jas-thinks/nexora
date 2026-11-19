"""Timed DSA mock interview. The interviewer (LLM or scripted) asks questions; Nexora records time, code runs and the transcript.
Scoring: rubric from an LLM when available (labelled as an ESTIMATE of reasoning quality; correctness is not verified), otherwise self-assessment only."""
import json
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import CodeRun, InterviewSession, MentorMessage
from app.models.catalog import Problem
from app.services import daily

DIMS = ("approach", "communication", "complexity", "edge_cases")


def _aw(d):
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def start(db: Session, user_id: int, minutes: int = 45, now: datetime | None = None) -> InterviewSession:
    if minutes not in (20, 30, 45, 60):
        raise ValueError("minutes must be 20, 30, 45 or 60")
    now = now or datetime.now(UTC)
    ctx = daily.build_ctx(db, user_id, now.date(), "interview", None, None)
    pool = [p for p in daily._pool(db, "interview", ctx.lo, ctx.hi, ctx.user_tier, ctx.sheet_ids) if p.id not in ctx.solved_ids and ctx.pmap.get(p.id)]
    ranked = daily.rank(ctx, pool)
    if not ranked:
        raise LookupError("No suitable interview problem found. Import a sheet (e.g. NeetCode) or sync a platform first.")
    s = InterviewSession(user_id=user_id, problem_id=ranked[0][1].id, minutes=minutes, started_at=now)
    db.add(s); db.commit()
    return s


def _thread(sid: int) -> str:
    return f"interview-{sid}"


def state(db: Session, user_id: int, sid: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    s = db.get(InterviewSession, sid)
    if s is None or s.user_id != user_id:
        raise LookupError("Interview not found")
    p = db.get(Problem, s.problem_id)
    left = 0 if s.status == "finished" else max(0, int((_aw(s.started_at) + timedelta(minutes=s.minutes) - now).total_seconds()))
    msgs = db.scalars(select(MentorMessage).where(MentorMessage.user_id == user_id, MentorMessage.thread == _thread(sid)).order_by(MentorMessage.id)).all()
    return {"id": s.id, "status": s.status, "minutes": s.minutes, "seconds_left": left, "overtime": s.status == "running" and left == 0,
            "problem": {"id": p.id, "name": p.name, "platform": p.platform, "rating": p.rating, "url": p.canonical_url or p.url, "note": "Open the problem on its platform; Nexora stores no statement. Describe it in your own words to the interviewer."},
            "transcript": [{"role": m.role, "content": m.content} for m in msgs], "rubric": s.rubric, "self_eval": s.self_eval}


def parse_rubric(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        r = {k: int(d[k]) for k in DIMS}
    except (ValueError, KeyError, TypeError):
        return None
    if any(not 1 <= v <= 5 for v in r.values()):
        return None
    return {"scores": r, "summary": str(d.get("summary", ""))[:500], "improvements": [str(x)[:200] for x in (d.get("improvements") or [])[:4]]}


RUBRIC_PROMPT = """Score this mock coding interview transcript. Judge ONLY what the candidate wrote. Return ONLY JSON:
{{"approach":1-5,"communication":1-5,"complexity":1-5,"edge_cases":1-5,"summary":"<=40 words","improvements":["<=15 words", "..."]}}
Be conservative: 3 is average, 5 is exceptional. If the candidate said nothing about a dimension, score it 1.
Problem: {name} ({platform}, rating {rating}).
<transcript>
{transcript}
</transcript>"""


def finish(db: Session, router, user_id: int, sid: int, self_eval: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    s = db.get(InterviewSession, sid)
    if s is None or s.user_id != user_id:
        raise LookupError("Interview not found")
    if s.status == "finished":
        return state(db, user_id, sid, now)
    p = db.get(Problem, s.problem_id)
    msgs = db.scalars(select(MentorMessage).where(MentorMessage.user_id == user_id, MentorMessage.thread == _thread(sid)).order_by(MentorMessage.id)).all()
    tr = "\n".join(f"{'Interviewer' if m.role == 'assistant' else 'Candidate'}: {m.content[:600]}" for m in msgs)[-6000:]
    rubric = None
    cand_turns = sum(m.role == "user" for m in msgs)
    if cand_turns >= 2:  # nothing meaningful to score otherwise
        res = router.chat(db, user_id, [{"role": "user", "content": RUBRIC_PROMPT.format(name=p.name, platform=p.platform, rating=p.rating, transcript=tr)}], purpose="interview", max_tokens=300)
        parsed = parse_rubric(res.text) if res else None
        if parsed:
            parsed["source"] = f"LLM estimate ({res.provider}); reasoning quality only, correctness is NOT verified"
            rubric = parsed
    runs = db.scalars(select(CodeRun).where(CodeRun.user_id == user_id, CodeRun.problem_id == p.id, CodeRun.created_at >= s.started_at)).all()
    used = int((now - _aw(s.started_at)).total_seconds())
    facts = {"time_used_seconds": used, "time_limit_seconds": s.minutes * 60, "candidate_turns": cand_turns, "code_runs": len(runs), "runs_by_verdict": {v: sum(r.verdict == v for r in runs) for v in {r.verdict for r in runs}},
             "note": "Code runs use your own tests in the sandbox; they show effort, not a verified solve."}
    s.rubric = {"measured": facts, "scored": rubric, "message": None if rubric else ("Not enough conversation to score." if cand_turns < 2 else "No LLM available to score: use the self-assessment below.")}
    if self_eval:
        s.self_eval = {k: v for k, v in self_eval.items() if k in DIMS and isinstance(v, int) and 1 <= v <= 5}
    s.status, s.ended_at = "finished", now
    db.commit()
    return state(db, user_id, sid, now)
