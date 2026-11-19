"""Difficulty-aware, weakness-targeted recommender (v1: transparent heuristic ranker).

Stage 1  candidates: unsolved rated problems inside the student's "zone of proximal development"
Stage 2  score: weakness of the problem's topics, difficulty fit, tag coverage/novelty
Stage 3  diversify (no more than 2 problems per primary tag) + explanations

This is a deterministic baseline. Its quality is measured by the offline harness
(see docs/ML_DESIGN.md) before any learned ranker replaces it.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import bkt
from app.models.catalog import Problem, ProblemStatus, TopicMastery
from app.models.user import utcnow

BANDS = [(800, 1000, "Warm-up"), (1000, 1300, "Foundation"), (1300, 1600, "Growth"),
         (1600, 1900, "Specialist"), (1900, 2200, "Expert push")]
IGNORED_TAGS = {"*special"}


def estimate_rating(solved_ratings: list[int]) -> tuple[int, str]:
    """Estimate = mean of the 5 hardest solved problems, minus a small margin (people solve
    slightly below their ceiling reliably). Returns (rating, confidence)."""
    if not solved_ratings:
        return 800, "none"
    top = sorted(solved_ratings, reverse=True)[:5]
    raw = sum(top) / len(top)
    # Shrink toward the 800 baseline until we have ~10 solves: 2 lucky solves must not claim 1500.
    w = min(1.0, len(solved_ratings) / 10)
    est = int(round((800 + (raw - 800) * w) / 100.0)) * 100
    conf = "low" if len(solved_ratings) < 10 else "medium" if len(solved_ratings) < 40 else "high"
    return max(800, est), conf


PRIOR_MEAN, PRIOR_SD, SCALE = 1000.0, 300.0, 200.0


def estimate_rating_map(outcomes: list[tuple[int, bool]]) -> tuple[int, str]:
    """MAP ability estimate (rating scale) from (problem_rating, solved) pairs, Elo/IRT-1PL style:
        P(solve | d) = sigmoid((r - d) / SCALE),  prior r ~ N(1000, 300^2).
    Uses failures as well as solves, so a few lucky hard solves cannot inflate it the way a 'hardest solved' statistic does.
    The prior keeps it sane with little data. Returns (rating rounded to 100, confidence by #outcomes)."""
    import math
    from collections import Counter
    xs = [(d, y) for d, y in outcomes if d is not None]
    if not xs:
        return 800, "none"
    buckets = Counter(xs)  # ratings are discrete: aggregate so cost is O(#distinct ratings), not O(#submissions)
    r = PRIOR_MEAN
    for _ in range(200):
        g = -(r - PRIOR_MEAN) / PRIOR_SD ** 2
        h = -1.0 / PRIOR_SD ** 2
        for (d, y), c in buckets.items():
            p = 1 / (1 + math.exp(-(r - d) / SCALE))
            g += c * ((1.0 if y else 0.0) - p) / SCALE
            h -= c * p * (1 - p) / SCALE ** 2
        step = max(-150.0, min(150.0, g / h))  # damped Newton: the objective is concave, damping prevents overshoot when saturated
        r = min(3600.0, max(500.0, r - step))
        if abs(step) < 0.01:
            break
    solved = [d for d, y in xs if y]
    if solved:  # selection-bias guardrail: failures may be unlogged (self-reports, sheets), so never credit more than hardest solve + 100
        r = min(r, max(solved) + 100)
    n = len(xs)
    return max(800, int(round(r / 100.0)) * 100), "low" if n < 10 else "medium" if n < 40 else "high"


def outcome_pairs(db: Session, user_id: int, as_of=None) -> list[tuple[int, bool]]:
    from app.patterns import mastery
    out = mastery.outcomes(db, user_id, as_of)
    if not out:
        return []
    rated = {pid: r for pid, r in db.execute(select(Problem.id, Problem.rating).where(Problem.id.in_(list(out)), Problem.rating.is_not(None)))}
    return [(rated[pid], o["solved"]) for pid, o in out.items() if pid in rated]


@dataclass
class Rec:
    problem: Problem
    score: float
    reasons: list[str]
    target_topic: str | None


def record_outcome(db: Session, user_id: int, problem: Problem, solved: bool, student_rating: int) -> None:
    st = db.scalar(select(ProblemStatus).where(ProblemStatus.user_id == user_id, ProblemStatus.problem_id == problem.id))
    if st is None:
        st = ProblemStatus(user_id=user_id, problem_id=problem.id)
        db.add(st)
    st.attempts = (st.attempts or 0) + 1
    st.solved = st.solved or solved
    st.updated_at = utcnow()
    db.commit()
    rebuild_mastery(db, user_id)  # single source of truth: replay of all events


def solved_ratings(db: Session, user_id: int) -> list[int]:
    q = (select(Problem.rating).join(ProblemStatus, ProblemStatus.problem_id == Problem.id)
         .where(ProblemStatus.user_id == user_id, ProblemStatus.solved.is_(True), Problem.rating.is_not(None)))
    return list(db.scalars(q))


def recommend(db: Session, user_id: int, count: int = 8, stretch: int = 100,
              topic: str | None = None, target_rating: int | None = None) -> dict:
    est, conf = estimate_rating_map(outcome_pairs(db, user_id))
    center = target_rating if target_rating else est
    lo, hi = center, center + 200 + stretch
    mastery = {m.topic: m for m in db.scalars(select(TopicMastery).where(TopicMastery.user_id == user_id))}
    done = set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user_id, ProblemStatus.solved.is_(True))))

    q = select(Problem).where(Problem.rating.is_not(None), Problem.rating >= lo, Problem.rating <= hi)
    cands = [p for p in db.scalars(q) if p.id not in done and (topic is None or topic in p.tags)]

    scored: list[Rec] = []
    for p in cands:
        tags = [t for t in p.tags if t not in IGNORED_TAGS] or ["implementation"]
        weakest = min(tags, key=lambda t: mastery[t].p_known if t in mastery else 0.2)
        wk = 1 - (mastery[weakest].p_known if weakest in mastery else 0.2)
        fit = 1 - abs((p.rating - (center + 100))) / 400  # ideal ~ +100 above estimate
        novelty = 0.15 if weakest not in mastery else 0.0
        score = 0.55 * wk + 0.35 * max(fit, 0) + novelty
        reasons = []
        if weakest in mastery:
            reasons.append(f"Targets '{weakest}' — your estimated mastery is {mastery[weakest].p_known:.0%}")
        else:
            reasons.append(f"New territory: you have no recorded attempts on '{weakest}'")
        reasons.append(f"Rated {p.rating}, {p.rating - est:+d} vs your estimated {est}"
                       + (" (stretch)" if p.rating > est + 100 else " (comfortable)" if p.rating <= est else ""))
        scored.append(Rec(p, score, reasons, weakest))
    scored.sort(key=lambda r: (-r.score, r.problem.id))

    picked, per_tag = [], {}
    for r in scored:
        if per_tag.get(r.target_topic, 0) >= 2:
            continue
        per_tag[r.target_topic] = per_tag.get(r.target_topic, 0) + 1
        picked.append(r)
        if len(picked) == count:
            break
    return {
        "estimated_rating": est, "confidence": conf, "window": [lo, hi],
        "note": "Rating is an estimate from your solved problems, not an official platform rating.",
        "items": [{"problem_id": r.problem.id, "name": r.problem.name, "rating": r.problem.rating,
                   "tags": r.problem.tags, "url": r.problem.url, "score": round(r.score, 3),
                   "target_topic": r.target_topic, "reasons": r.reasons} for r in picked],
    }


def rebuild_mastery(db: Session, user_id: int) -> int:
    """Recompute TopicMastery by replaying the full event history in time order.
    Deterministic and idempotent: re-syncing the same data yields identical mastery (no double counting).
    One BKT update per problem outcome (first AC => success; otherwise a single failure), with forgetting decay
    applied between events on the same topic."""
    from collections import defaultdict
    from datetime import UTC
    from app.models.integrations import Submission

    probs = {p.id: p for p in db.scalars(select(Problem))}
    by_problem: dict[int, list] = defaultdict(list)
    for sid, pid, verdict, at in db.execute(select(Submission.id, Submission.problem_id, Submission.verdict, Submission.submitted_at)
                                            .where(Submission.user_id == user_id, Submission.problem_id.is_not(None))):
        by_problem[pid].append((at if at.tzinfo else at.replace(tzinfo=UTC), verdict))
    events = []  # (time, problem, solved)
    for pid, subs in by_problem.items():
        subs.sort()
        ac = next((t for t, v in subs if v == "AC"), None)
        events.append((ac, pid, True) if ac else (subs[-1][0], pid, False))
    seen = set(by_problem)
    for st in db.scalars(select(ProblemStatus).where(ProblemStatus.user_id == user_id, ProblemStatus.provenance == "self_reported")):
        if st.problem_id not in seen:  # self-reported outcomes count when no verified record exists
            events.append((st.updated_at if st.updated_at.tzinfo else st.updated_at.replace(tzinfo=UTC), st.problem_id, st.solved))
    events.sort(key=lambda e: (e[0], e[1]))

    state: dict[str, tuple[float, int, object]] = {}  # topic -> (p_known, attempts, last_time)
    solved_r: list[int] = []
    base = bkt.BKTParams()
    for t, pid, solved in events:
        p = probs.get(pid)
        if p is None:
            continue
        est, _ = estimate_rating(solved_r)
        params = bkt.difficulty_adjusted(base, (p.rating or est) - est)
        for tag in p.tags:
            if tag in IGNORED_TAGS:
                continue
            pk, n, last = state.get(tag, (base.p_init, 0, None))
            if last is not None:
                pk = bkt.decay(pk, (t - last).total_seconds() / 86400, base)
            state[tag] = (bkt.update(pk, solved, params), n + 1, t)
        if solved and p.rating:
            solved_r.append(p.rating)
    for tm in db.scalars(select(TopicMastery).where(TopicMastery.user_id == user_id)):
        if tm.topic not in state:
            db.delete(tm)
    existing = {m.topic: m for m in db.scalars(select(TopicMastery).where(TopicMastery.user_id == user_id))}
    for topic, (pk, n, last) in state.items():
        m = existing.get(topic) or TopicMastery(user_id=user_id, topic=topic)
        m.p_known, m.attempts, m.updated_at = pk, n, last
        db.add(m)
    db.commit()
    return len(state)
