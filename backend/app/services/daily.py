"""Daily Challenge engine (policy daily-v1): personalised, multi-objective, explainable, feedback-aware.

Objectives (each scored 0..1 per candidate from real student features):
  weakness, reinforcement, revision, progression, diversity, exploration
Weights depend on mode and on how much evidence exists (cold start emphasises exploration + progression on easy problems).
The explanation is generated from the same feature values that produced the score, never from free text.
"""
import hashlib
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, ProblemStatus, SheetItem
from app.models.daily import DailyChallenge, ReviewItem
from app.patterns import mastery
from app.patterns.mastery import PState, tier
from app.patterns.taxonomy import BY_ID, PATTERNS
from app.services import recommender

POLICY = "daily-v1"
MODES = ("personalized", "cp", "interview", "revision", "topic")
PATHS = {"beginner": -100, "intermediate": 100, "advanced": 300}  # offset from estimated rating
BOX_DAYS = [1, 3, 7, 21, 60]
WEIGHTS = {
    "personalized": dict(weakness=.30, reinforcement=.15, revision=.15, progression=.20, diversity=.10, exploration=.10),
    "cp": dict(weakness=.30, reinforcement=.10, revision=.10, progression=.30, diversity=.10, exploration=.10),
    "interview": dict(weakness=.30, reinforcement=.20, revision=.15, progression=.15, diversity=.10, exploration=.10),
    "revision": dict(weakness=.10, reinforcement=.10, revision=.60, progression=.05, diversity=.10, exploration=.05),
    "topic": dict(weakness=.35, reinforcement=.15, revision=.10, progression=.25, diversity=.00, exploration=.15),
}
COLD = dict(weakness=.05, reinforcement=.00, revision=.00, progression=.45, diversity=.10, exploration=.40)


def _seed(user_id: int, day: date, pid: int) -> float:
    """Deterministic tie-break: stable for a (user, day, problem) but varies across users/days."""
    return int(hashlib.sha256(f"{user_id}|{day}|{pid}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _friction(db: Session, user_id: int) -> dict[str, float]:
    """Patterns where recent completed challenges needed many hints / felt hard => hold difficulty back there."""
    out: dict[str, list[float]] = {}
    rows = db.scalars(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.status == "completed")
                      .order_by(DailyChallenge.day.desc()).limit(15)).all()
    for r in rows:
        fb = r.feedback or {}
        f = min(1.0, (fb.get("hints_used", 0) / 4) * 0.5 + ((fb.get("self_difficulty", 3) - 1) / 4) * 0.5
                + (0.2 if fb.get("editorial_viewed") else 0) + (0.2 if not fb.get("solved", True) else 0))
        if r.primary_pattern:
            out.setdefault(r.primary_pattern, []).append(f)
    return {k: sum(v) / len(v) for k, v in out.items()}


def _pool(db: Session, mode: str, lo: int, hi: int, user_tier: int, sheet_ids: set[int]) -> list[Problem]:
    q = select(Problem).where(Problem.status == "active")
    if mode in ("cp",):
        q = q.where(Problem.platform == "codeforces", Problem.rating.between(lo, hi))
        return list(db.scalars(q))
    rows = list(db.scalars(q.where(Problem.rating.between(lo, hi), Problem.platform == "codeforces"))) if mode != "interview" else []
    sheet_probs = [p for p in db.scalars(select(Problem).where(Problem.id.in_(sheet_ids))) if p.status == "active"] if sheet_ids else []
    for p in sheet_probs:
        t = tier(p)
        if p.rating is None and t is not None and user_tier - 1 <= t <= user_tier + 1:
            rows.append(p)
        elif p.rating is not None and lo <= p.rating <= hi and p not in rows:
            rows.append(p)
    return rows


from dataclasses import dataclass


@dataclass
class Ctx:
    user_id: int
    day: date
    mode: str
    topic: str | None
    states: dict
    out: dict
    est: int
    conf: str
    center: int
    lo: int
    hi: int
    user_tier: int
    w: dict
    cold: bool
    pmap: dict
    recent_pats: list
    friction: dict
    due_ids: set
    solved_ids: set
    recent_pids: set
    sheet_ids: set


def build_ctx(db: Session, user_id: int, day: date, mode: str, path: str | None, topic: str | None, as_of: datetime | None = None) -> Ctx:
    """as_of!=None => evaluation mode: only evidence before as_of, no stored-BKT (it would leak the future)."""
    now = as_of or (datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=12))
    states = mastery.assess_cached(db, user_id, now) if as_of is None else mastery.assess_all(db, user_id, now, as_of=as_of, use_tracing=False)
    out = mastery.outcomes(db, user_id, as_of)
    solved_ids = {pid for pid, o in out.items() if o["solved"]}
    est, conf = recommender.estimate_rating_map(recommender.outcome_pairs(db, user_id, as_of))  # same evidence source as pattern mastery
    cold = len(solved_ids) < 5
    w = dict(COLD if cold and mode != "revision" else WEIGHTS[mode])
    off = PATHS.get(path or "", 100)
    if cold and not path:
        off = -100
    center = est + off
    recent = list(db.scalars(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.day >= day - timedelta(days=14),
                                                           DailyChallenge.day < day, DailyChallenge.status != "swapped")))
    due_ids = {r.problem_id for r in db.scalars(select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.due_at <= now))} if as_of is None else set()
    return Ctx(user_id, day, mode, topic, states, out, est, conf, center, max(800, center - 100), center + 200,
               1 if est < 1200 else 2 if est < 1800 else 3, w, cold, mastery.problem_patterns(db), [r.primary_pattern for r in recent if r.primary_pattern][-7:],
               _friction(db, user_id) if as_of is None else {}, due_ids, solved_ids, {r.problem_id for r in recent},
               set(db.scalars(select(SheetItem.problem_id))))


def score_problem(c: Ctx, p: Problem):
    """-> (score, primary_pattern, features) or None. The single scoring function used in production AND offline evaluation."""
    pats = [x for x in c.pmap.get(p.id, []) if x in c.states]
    if not pats:
        return None
    if c.topic and c.topic in pats:
        pats = [c.topic] + [x for x in pats if x != c.topic]

    def need(x: str) -> float:
        st = c.states[x]
        return {"weak": 1.0, "learning": 0.8, "unexplored": 0.6, "practised": 0.4, "mastered": 0.1}[st.status] + (0.5 if st.due_for_revision else 0)
    prim = max(pats, key=need)
    s = c.states[prim]
    weakness = {"weak": 1.0, "learning": 0.7}.get(s.status, 0.0) * (1 - s.score * 0.5)
    reinforcement = 0.8 if s.status == "practised" else 0.3 if s.status == "learning" else 0.0
    revision = 1.0 if (p.id in c.due_ids or s.due_for_revision) else 0.0
    t = tier(p)
    if p.rating is not None:
        fit = max(0.0, 1 - abs(p.rating - (c.center + friction_adj(c.friction.get(prim, 0.0)))) / 300)
    else:
        fit = 1.0 if t == c.user_tier else 0.6 if t == c.user_tier + 1 else 0.4 if t == c.user_tier - 1 else 0.1
    diversity = 1 - (c.recent_pats.count(prim) / len(c.recent_pats)) if c.recent_pats else 1.0
    exploration = 1.0 if s.status == "unexplored" and not s.missing_prereqs else 0.0
    feat = dict(weakness=weakness, reinforcement=reinforcement, revision=revision, progression=fit, diversity=diversity, exploration=exploration)
    score = sum(c.w[k] * v for k, v in feat.items())
    if s.missing_prereqs and s.status == "unexplored":
        score *= 0.35  # don't open a pattern whose prerequisites are unexplored; train the prerequisite instead
    if c.topic and c.topic in c.pmap.get(p.id, []):
        score += 0.3
    score += 0.001 * _seed(c.user_id, c.day, p.id)
    return score, prim, {**feat, "total": round(score, 4)}


def rank(c: Ctx, pool: list[Problem]) -> list[tuple[float, Problem, str, dict]]:
    scored = [(r[0], p, r[1], r[2]) for p in pool if (r := score_problem(c, p)) is not None]
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return scored


def generate(db: Session, user_id: int, day: date | None = None, mode: str = "personalized", path: str | None = None,
             topic: str | None = None, exclude: frozenset[int] = frozenset()) -> DailyChallenge:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if topic and (topic not in BY_ID or BY_ID[topic].kind == "category"):
        raise ValueError("unknown pattern")
    if mode == "topic" and not topic:
        raise ValueError("topic mode needs a pattern id")
    if path and path not in PATHS:
        raise ValueError(f"path must be one of {list(PATHS)}")
    day = day or datetime.now(UTC).date()
    existing = db.scalar(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.day == day, DailyChallenge.mode == mode,
                                                      DailyChallenge.status != "swapped"))
    if existing:
        # A cold-start pick (made before any evidence existed) must not freeze the day once the student syncs real data.
        was_cold = (existing.objective_scores or {}).get("cold")
        if was_cold is None:  # rows created before the flag existed: infer from the stored explanation
            was_cold = any("starting gently" in w for w in (existing.explanation or {}).get("why", []))
        if existing.status == "assigned" and was_cold:
            if not build_ctx(db, user_id, day, mode, path, topic).cold:
                existing.status, existing.feedback = "swapped", {"swap_reason": "evidence_updated"}
                db.commit()
                existing = None
        if existing:
            return existing  # idempotent: one challenge per user/day/mode

    c = build_ctx(db, user_id, day, mode, path, topic)
    if mode == "revision":
        pool = list(db.scalars(select(Problem).where(Problem.id.in_(c.due_ids)))) if c.due_ids else []
        if not pool:
            raise LookupError("Nothing is due for revision yet. Complete and review a few problems first.")
    else:
        pool = [p for p in _pool(db, mode, c.lo, c.hi, c.user_tier, c.sheet_ids)
                if p.id not in c.solved_ids and p.id not in c.recent_pids and p.id not in exclude]
        if mode == "topic":
            pool = [p for p in pool if topic in c.pmap.get(p.id, [])]
        elif c.due_ids and mode in ("personalized", "interview"):
            pool += [p for p in db.scalars(select(Problem).where(Problem.id.in_(c.due_ids))) if p.id not in c.recent_pids and p.id not in exclude]
    pool = [p for p in pool if c.pmap.get(p.id)]
    if not pool:
        raise LookupError("No suitable unsolved problems found. Sync the catalog / import a sheet, or widen the difficulty path.")
    ranked = rank(c, pool)
    if not ranked:
        raise LookupError("No candidate could be mapped to a pattern.")
    from app.services import experiment
    arm, in_analysis = experiment.arm_for(db, user_id)
    if arm == "control" and mode == "personalized":  # baseline: closest to the student's level, no personalisation terms
        base = sorted(ranked, key=lambda r: (abs((r[1].rating or c.center + 100) - (c.est + 100)), r[1].id))[0]
        score, p, prim, feat = base
        ex = {"why": [f"A problem near your estimated level ({c.est})."], "pattern": {"id": prim, "name": BY_ID[prim].name, "kind": BY_ID[prim].kind, "status": c.states[prim].status, "score": c.states[prim].score},
              "difficulty": f"Rated {p.rating}" if p.rating else f"Source difficulty: {p.source_difficulty or 'unknown'}", "prerequisites": [], "prerequisite_gaps": [], "connects_to": [],
              "connection_note": "", "after_this": ["Try one with a slightly higher rating."], "top_objectives": [], "evidence": [], "mode": mode, "policy": "baseline-rating-matched-v1", "data_confidence": f"rating estimate confidence: {c.conf}"}
    else:
        arm = "treatment" if arm == "control" else arm  # non-personalised modes always use the full policy
        score, p, prim, feat = ranked[0]
        ex = explain(db, user_id, p, prim, c.states, c.est, c.conf, mode, c.w, feat, c.out, c.pmap, c.cold, p.id in c.due_ids, c.friction.get(prim))
    ch = DailyChallenge(user_id=user_id, day=day, mode=mode, problem_id=p.id, primary_pattern=prim,
                        objective_scores={"weights": c.w, "features": feat, "cold": c.cold, "arm": arm}, explanation=ex, policy_version=ex.get("policy", POLICY))
    db.add(ch); db.flush()
    from app.models.ai import RecommendationLog
    db.add(RecommendationLog(user_id=user_id, challenge_id=ch.id, problem_id=p.id, arm=arm, policy=ex.get("policy", POLICY), pattern=prim, est_rating=c.est,
                             in_analysis=in_analysis and mode == "personalized"))
    db.commit()
    return ch


def friction_adj(f: float) -> float:
    return -150 * f  # up to 150 rating points easier where the student recently struggled


def explain(db, user_id, p: Problem, prim: str, states: dict[str, PState], est, conf, mode, w, feat, out, pmap, cold, was_due, fr) -> dict:
    s, pat = states[prim], BY_ID[prim]
    why: list[str] = []
    if was_due:
        why.append("Spaced-repetition review is due for this problem.")
    if cold:
        why.append(f"You have few recorded solves, so Nexora is starting gently (estimated rating {est}, confidence {conf}) and exploring '{pat.name}'.")
    elif s.status == "weak":
        why.append(f"'{pat.name}' is currently a weakness: {s.solved} solved of {s.attempted} attempted distinct problems (smoothed accuracy {s.accuracy:.0%}).")
    elif s.status == "learning":
        why.append(f"'{pat.name}' is still being learned (mastery score {s.score:.2f}, {s.solved} solved).")
    elif s.status == "practised":
        why.append(f"'{pat.name}' is practised but not yet mastered (score {s.score:.2f}); this reinforces it with a different problem.")
    elif s.status == "unexplored":
        why.append(f"'{pat.name}' is unexplored for you, and its prerequisites look ready.")
    else:
        why.append(f"'{pat.name}' is mastered; this is a maintenance rep.")
    if s.due_for_revision:
        why.append(f"You haven't touched it for {s.days_idle} days.")
    diff = f"Rated {p.rating} ({p.rating - est:+d} vs your estimated {est})" if p.rating is not None else f"Source difficulty: {p.source_difficulty or 'unknown'}"
    if fr is not None and fr > 0.4:
        diff += "; held back because recent challenges on this pattern felt hard or needed many hints"
    prereq = [{"pattern": q, "name": BY_ID[q].name, "status": states[q].status} for q in pat.prereq if q in states]
    solved_related = []
    for pid, o in out.items():
        if o["solved"] and prim in pmap.get(pid, []):
            solved_related.append(pid)
    related_titles = [x.name for x in db.scalars(select(Problem).where(Problem.id.in_(solved_related[:50])))][:3] if solved_related else []
    nxt = [q.id for q in PATTERNS if prim in q.prereq and q.kind != "category" and states.get(q.id) and states[q.id].status == "unexplored"][:3]
    top_obj = sorted(((k, v * w[k]) for k, v in feat.items() if k != "total"), key=lambda kv: -kv[1])[:3]
    return {
        "why": why, "pattern": {"id": prim, "name": pat.name, "kind": pat.kind, "status": s.status, "score": s.score},
        "difficulty": diff, "prerequisites": prereq,
        "prerequisite_gaps": [q["name"] for q in prereq if q["status"] in ("unexplored", "weak")],
        "connects_to": related_titles, "connection_note": (f"You already solved {len(solved_related)} problem(s) in this pattern, e.g. " + ", ".join(related_titles)) if related_titles else "No solved problem in this pattern yet.",
        "after_this": [BY_ID[q].name for q in nxt] or ["Try the same pattern one difficulty step higher."],
        "top_objectives": [{"objective": k, "contribution": round(v, 3)} for k, v in top_obj],
        "evidence": s.reasons, "mode": mode, "policy": POLICY,
        "data_confidence": f"rating estimate confidence: {conf}",
    }


def swap(db: Session, ch: DailyChallenge, reason: str) -> DailyChallenge:
    """One swap per day (same mode). The old row is kept as history; the old problem is excluded from the new pick."""
    if ch.swaps >= 1:
        raise PermissionError("Only one swap per day.")
    if ch.status != "assigned":
        raise PermissionError("Challenge is already completed, skipped or swapped.")
    uid, day, mode, old = ch.user_id, ch.day, ch.mode, ch.problem_id
    topic = ch.primary_pattern if mode == "topic" else None
    ch.status, ch.feedback = "swapped", {"swap_reason": reason[:200]}
    db.commit()
    try:
        new = generate(db, uid, day, mode, None, topic, exclude=frozenset({old}))
    except LookupError:
        ch.status, ch.feedback = "assigned", {}  # nothing else suitable: keep the original rather than leave the day empty
        db.commit()
        raise
    new.swaps = 1
    db.commit()
    return new


def complete(db: Session, ch: DailyChallenge, solved: bool, hints_used: int = 0, editorial_viewed: bool = False,
             self_difficulty: int = 3, understanding: int | None = None, minutes: int | None = None) -> DailyChallenge:
    st = db.scalar(select(ProblemStatus).where(ProblemStatus.user_id == ch.user_id, ProblemStatus.problem_id == ch.problem_id))
    if st is None:
        st = ProblemStatus(user_id=ch.user_id, problem_id=ch.problem_id); db.add(st)
    st.attempts, st.solved = (st.attempts or 0) + 1, st.solved or solved
    st.updated_at = datetime.now(UTC)
    ch.status, ch.completed_at = "completed", datetime.now(UTC)
    ch.feedback = {"solved": solved, "hints_used": hints_used, "editorial_viewed": editorial_viewed, "self_difficulty": self_difficulty,
                   "understanding": understanding, "minutes": minutes}
    # spaced repetition: success with good understanding & few hints climbs a box; otherwise review again tomorrow
    rv = db.scalar(select(ReviewItem).where(ReviewItem.user_id == ch.user_id, ReviewItem.problem_id == ch.problem_id))
    good = solved and (understanding or 3) >= 3 and hints_used <= 2 and not editorial_viewed
    box = 0 if rv is None else rv.box
    box = min(box + 1, len(BOX_DAYS) - 1) if good else 0
    due = datetime.now(UTC) + timedelta(days=BOX_DAYS[box])
    if rv is None:
        db.add(ReviewItem(user_id=ch.user_id, problem_id=ch.problem_id, due_at=due, box=box, last_result="good" if good else "again"))
    else:
        rv.due_at, rv.box, rv.last_result = due, box, "good" if good else "again"
    db.commit()
    recommender.rebuild_mastery(db, ch.user_id)
    return ch


def verify_solves(db: Session, user_id: int, now: datetime | None = None) -> int:
    """After a platform sync: a challenge whose problem has a VERIFIED accepted submission after it was assigned is completed/verified automatically."""
    from app.models.integrations import Submission
    now = now or datetime.now(UTC)
    n = 0
    for ch in db.scalars(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.status.in_(("assigned", "completed")),
                                                       DailyChallenge.created_at >= now - timedelta(days=30))):
        if (ch.feedback or {}).get("verified"):
            continue
        at = ch.created_at if ch.created_at.tzinfo else ch.created_at.replace(tzinfo=UTC)
        ac = db.scalar(select(Submission.submitted_at).where(Submission.user_id == user_id, Submission.problem_id == ch.problem_id, Submission.verdict == "AC",
                                                             Submission.provenance == "verified", Submission.submitted_at >= at).order_by(Submission.submitted_at).limit(1))
        if ac is None:
            continue
        fb = dict(ch.feedback or {})
        if ch.status == "assigned":
            ch.status, ch.completed_at = "completed", ac
            fb.update(solved=True, auto=True)
            rv = db.scalar(select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.problem_id == ch.problem_id))
            if rv is None:
                db.add(ReviewItem(user_id=user_id, problem_id=ch.problem_id, due_at=now + timedelta(days=BOX_DAYS[1]), box=1, last_result="good"))
        fb["verified"] = True
        ch.feedback = fb
        n += 1
    db.commit()
    return n
