"""Pattern mastery from MULTIPLE evidence signals (never from solved count alone), with a written explanation.

Signals per pattern:
  coverage   distinct problems solved (saturating)         weight .30
  accuracy   smoothed solved/attempted over distinct problems   .25   ((s+1)/(a+2): few attempts => pulled to 0.5)
  breadth    difficulty tiers solved (easy/medium/hard)      .20
  tracing    mean BKT topic mastery of the pattern's tags    .25
Status thresholds are explicit and returned with every result so a verdict can always be traced to numbers.
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, ProblemStatus, SheetItem, TopicMastery
from app.models.integrations import Submission
from app.patterns.mapping import observable_patterns, patterns_for
from app.patterns.taxonomy import PATTERNS

REVISION_AFTER_DAYS = 30
MASTERED_SCORE, MASTERED_SOLVED, PRACTISED_SCORE = 0.70, 5, 0.40
TIER_LABELS = {"easy": 1, "medium": 2, "hard": 3}


def tier(p: Problem) -> int | None:
    """1/2/3 from rating (CF-style) or the source's own Easy/Medium/Hard label. None = unknown (never guessed)."""
    if p.rating is not None:
        return 1 if p.rating < 1200 else 2 if p.rating < 1800 else 3
    return TIER_LABELS.get((p.source_difficulty or "").strip().lower())


@dataclass
class PState:
    pattern: str
    status: str  # unexplored | learning | practised | mastered | weak
    score: float
    solved: int = 0
    attempted: int = 0
    accuracy: float | None = None
    tiers: list[int] = field(default_factory=list)
    last_activity: datetime | None = None
    due_for_revision: bool = False
    days_idle: int | None = None
    bkt: float | None = None
    reasons: list[str] = field(default_factory=list)
    missing_prereqs: list[str] = field(default_factory=list)


def _aw(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


_PM_CACHE: dict = {}
_ASSESS_CACHE: dict = {}
_LOCKS: dict = {}
_CATALOG_VERSION = [0]


def bump_catalog() -> None:
    """Call after any write to problems/sheets so cached pattern maps and assessments are recomputed."""
    _CATALOG_VERSION[0] += 1
    _PM_CACHE.clear(); _ASSESS_CACHE.clear(); _EST_CACHE.clear()


def problem_patterns(db: Session) -> dict[int, list[str]]:
    """problem id -> patterns. Cached per catalog version (problem + membership counts); a known scaling hotspot."""
    from sqlalchemy import func
    from app.models.ai import ProblemPatternLabel
    key = (db.scalar(select(func.count()).select_from(ProblemPatternLabel).where(ProblemPatternLabel.status == "accepted")), db.scalar(select(func.count()).select_from(Problem)), db.scalar(select(func.max(Problem.id))),
           db.scalar(select(func.count()).select_from(SheetItem)), db.scalar(select(func.max(SheetItem.id))), _CATALOG_VERSION[0])
    if _PM_CACHE.get("key") == key:
        return _PM_CACHE["val"]
    secs: dict[int, list[str]] = defaultdict(list)
    for pid, sec in db.execute(select(SheetItem.problem_id, SheetItem.section)):
        secs[pid].append(sec)
    from app.patterns.labeling import accepted_map
    acc = accepted_map(db)  # reviewed (or explicit-keyword) problem-level labels extend the tag/section evidence
    val = {}
    for p in db.scalars(select(Problem)):
        ps = patterns_for(p.tags, secs.get(p.id, []))
        val[p.id] = ps + [x for x in acc.get(p.id, []) if x not in ps]
    _PM_CACHE.update(key=key, val=val)
    return val


def outcomes(db: Session, user_id: int, as_of: datetime | None = None) -> dict[int, dict]:
    """Per distinct problem: attempts, solved, first_try, last_at, tier."""
    out: dict[int, dict] = {}
    q = select(Submission.problem_id, Submission.verdict, Submission.submitted_at).where(Submission.user_id == user_id, Submission.problem_id.is_not(None))
    rows = [r for r in db.execute(q.order_by(Submission.submitted_at)).all() if as_of is None or _aw(r[2]) < as_of]
    for pid, verdict, at in rows:
        o = out.setdefault(pid, {"attempts": 0, "solved": False, "first_try": False, "last_at": None})
        if o["attempts"] == 0 and verdict == "AC":
            o["first_try"] = True
        o["attempts"] += 1
        o["solved"] = o["solved"] or verdict == "AC"
        o["last_at"] = _aw(at)
    for st in db.scalars(select(ProblemStatus).where(ProblemStatus.user_id == user_id)):
        if st.problem_id in out or (as_of is not None and _aw(st.updated_at) >= as_of):
            continue  # verified record wins over self-report; as_of excludes the future
        out[st.problem_id] = {"attempts": max(st.attempts, 1), "solved": st.solved, "first_try": st.solved and st.attempts <= 1,
                              "last_at": _aw(st.updated_at)}
    return out


def _labelled(db: Session) -> set[str]:
    from app.models.ai import ProblemPatternLabel
    return set(db.scalars(select(ProblemPatternLabel.pattern_id).where(ProblemPatternLabel.status == "accepted").distinct()))


def assess_all(db: Session, user_id: int, now: datetime | None = None, as_of: datetime | None = None,
               use_tracing: bool = True) -> dict[str, PState]:
    """as_of: only evidence strictly before this instant (evaluation). use_tracing=False ignores the stored BKT table,
    which is computed from ALL history and would leak the future."""
    now = now or datetime.now(UTC)
    out_all = outcomes(db, user_id, as_of)
    probs: dict[int, Problem] = {}
    ids = list(out_all)
    for i in range(0, len(ids), 900):  # only the problems this student touched, not the whole catalog
        probs.update({p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(ids[i:i + 900])))})
    pmap = problem_patterns(db)
    tags_mastery = {m.topic: m.p_known for m in db.scalars(select(TopicMastery).where(TopicMastery.user_id == user_id))} if use_tracing else {}
    acc: dict[str, dict] = defaultdict(lambda: {"solved": set(), "attempted": set(), "tiers": set(), "last": None})
    for pid, o in out_all.items():
        p = probs.get(pid)
        if p is None:
            continue
        for pat in pmap.get(pid, []):
            a = acc[pat]
            a["attempted"].add(pid)
            if o["solved"]:
                a["solved"].add(pid)
                if (t := tier(p)) is not None:
                    a["tiers"].add(t)
            a["last"] = max(filter(None, [a["last"], o["last_at"]]), default=None)

    labelled = _labelled(db)
    states: dict[str, PState] = {}
    for pat in PATTERNS:
        if pat.kind == "category":
            continue
        a = acc.get(pat.id)
        if a is None:
            if pat.id in observable_patterns() or pat.id in labelled:
                states[pat.id] = PState(pat.id, "unexplored", 0.0, reasons=["No recorded attempts on any problem mapped to this pattern."])
            else:
                states[pat.id] = PState(pat.id, "unmeasured", 0.0, reasons=["No platform tag or sheet section maps to this pattern yet, so Nexora cannot measure it. This is a taxonomy/data gap, not a statement about you."])
            continue
        s, n = len(a["solved"]), len(a["attempted"])
        accuracy = (s + 1) / (n + 2)
        cov = 1 - math.exp(-s / 4)
        breadth = len(a["tiers"]) / 3
        tm = [tags_mastery[t] for t in pat.cf_tags if t in tags_mastery]
        bkt = sum(tm) / len(tm) if tm else None
        score = 0.30 * cov + 0.25 * accuracy + 0.20 * breadth + 0.25 * (bkt if bkt is not None else accuracy)
        idle = (now - a["last"]).days if a["last"] else None
        if s >= MASTERED_SOLVED and score >= MASTERED_SCORE and len(a["tiers"]) >= 2:
            status = "mastered"
        elif n >= 3 and accuracy < 0.40:
            status = "weak"
        elif s == 0 and n >= 2:
            status = "weak"
        elif score >= PRACTISED_SCORE:
            status = "practised"
        else:
            status = "learning"
        st = PState(pat.id, status, round(score, 3), s, n, round(accuracy, 3), sorted(a["tiers"]), a["last"],
                    status in ("practised", "mastered") and idle is not None and idle > REVISION_AFTER_DAYS, idle,
                    None if bkt is None else round(bkt, 3))
        st.reasons = [f"Solved {s} of {n} distinct problems (smoothed accuracy {accuracy:.0%}).",
                      f"Difficulty tiers solved: {sorted(a['tiers']) or 'none'} of 1-3."]
        if bkt is not None:
            st.reasons.append(f"Knowledge-tracing estimate for its tags: {bkt:.0%}.")
        if status == "mastered":
            st.reasons.append(f"Mastered because score {score:.2f} ≥ {MASTERED_SCORE}, ≥{MASTERED_SOLVED} solved and ≥2 difficulty tiers.")
        if status == "weak":
            st.reasons.append("Weak because accuracy is low over several distinct problems" if n >= 3 else "Weak because attempts have not yet produced a solve.")
        if st.due_for_revision:
            st.reasons.append(f"Due for revision: no activity for {idle} days (threshold {REVISION_AFTER_DAYS}).")
        states[pat.id] = st
    for pat in PATTERNS:  # prerequisite gaps, computed after all states exist
        if pat.id in states:
            states[pat.id].missing_prereqs = [q for q in pat.prereq if q in states and states[q].status in ("unexplored", "weak", "learning")]
    return states


def coverage(states: dict[str, PState]) -> dict:
    from collections import Counter
    c = Counter(s.status for s in states.values())
    return {"total_patterns": len(states), "by_status": dict(c), "due_for_revision": sum(s.due_for_revision for s in states.values()),
            "note": "Taxonomy v0.1 is authored and unreviewed; counts describe this taxonomy, not the whole field."}


def assess_cached(db: Session, user_id: int, now: datetime | None = None) -> dict[str, PState]:
    """Production path: assess_all memoised per user, invalidated by any change to that user's evidence or the catalog."""
    from sqlalchemy import func
    now = now or datetime.now(UTC)
    fp = (user_id, now.date().isoformat(), _CATALOG_VERSION[0],
          db.execute(select(func.count(), func.max(Submission.id)).where(Submission.user_id == user_id)).one(),
          db.execute(select(func.count(), func.max(ProblemStatus.updated_at)).where(ProblemStatus.user_id == user_id)).one(),
          db.scalar(select(func.max(TopicMastery.updated_at)).where(TopicMastery.user_id == user_id)))
    hit = _ASSESS_CACHE.get(user_id)
    if hit and hit[0] == fp:
        return hit[1]
    import threading
    with _LOCKS.setdefault(user_id, threading.Lock()):  # single-flight: concurrent cold requests compute once, the rest reuse it
        hit = _ASSESS_CACHE.get(user_id)
        if hit and hit[0] == fp:
            return hit[1]
        val = assess_all(db, user_id, now)
        if len(_ASSESS_CACHE) > 500:
            _ASSESS_CACHE.pop(next(iter(_ASSESS_CACHE)))
        _ASSESS_CACHE[user_id] = (fp, val)
        return val


_EST_CACHE: dict = {}


def evidence_fingerprint(db: Session, user_id: int) -> tuple:
    from sqlalchemy import func
    return (user_id, _CATALOG_VERSION[0],
            db.execute(select(func.count(), func.max(Submission.id)).where(Submission.user_id == user_id)).one(),
            db.execute(select(func.count(), func.max(ProblemStatus.updated_at)).where(ProblemStatus.user_id == user_id)).one())


def estimate_cached(db: Session, user_id: int) -> tuple[int, str]:
    """Rating estimate memoised per user; invalidated by any change to that user's evidence or the catalog."""
    from app.services import recommender
    fp = evidence_fingerprint(db, user_id)
    hit = _EST_CACHE.get(user_id)
    if hit and hit[0] == fp:
        return hit[1]
    val = recommender.estimate_rating_map(recommender.outcome_pairs(db, user_id))
    if len(_EST_CACHE) > 2000:
        _EST_CACHE.pop(next(iter(_EST_CACHE)))
    _EST_CACHE[user_id] = (fp, val)
    return val
