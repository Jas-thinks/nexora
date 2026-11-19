"""30/60-day interview crash course: a day-by-day plan built from REAL data (what the target companies reportedly ask, what the student has already solved).

Deterministic and explainable: no LLM, no invented problems. Every DSA task is a problem in the catalog; every design task is a library question or a first-party note.
It promises no outcome. It is a schedule that spends limited time on the highest-value material."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Problem, ProblemStatus
from app.models.resources import Company, CompanyProblem, CrashCourse, DesignQuestion
from app.resources import design_questions
from app.resources.tiers import TIER_LABELS

DSA_TOPICS = [  # id, title, LeetCode topic tags (as ingested), relative weight
    ("arrays-hashing", "Arrays, strings & hashing", ["Array", "Hash Table", "String", "Prefix Sum"], 1.3),
    ("two-pointers", "Two pointers", ["Two Pointers"], 0.8),
    ("sliding-window", "Sliding window", ["Sliding Window"], 0.8),
    ("stack-queue", "Stack, queue & monotonic stack", ["Stack", "Monotonic Stack", "Queue"], 0.8),
    ("binary-search", "Binary search", ["Binary Search"], 0.9),
    ("linked-list", "Linked lists", ["Linked List"], 0.7),
    ("trees", "Trees & BST", ["Tree", "Binary Tree", "Binary Search Tree"], 1.3),
    ("heap", "Heap / priority queue", ["Heap (Priority Queue)"], 0.7),
    ("graphs", "Graphs, BFS/DFS & union-find", ["Graph Theory", "Breadth-First Search", "Depth-First Search", "Union-Find", "Matrix"], 1.4),
    ("backtracking", "Backtracking & recursion", ["Backtracking", "Recursion"], 0.8),
    ("dp", "Dynamic programming", ["Dynamic Programming"], 1.5),
    ("greedy", "Greedy & sorting", ["Greedy", "Sorting"], 0.9),
    ("trie-bits", "Trie & bit manipulation", ["Trie", "Bit Manipulation"], 0.5),
    ("design-ds", "Design-style data-structure problems", ["Design"], 0.5),
]
SD_CONCEPTS = [  # note slug (rag/design_notes), title
    ("requirements", "Requirements & scope"), ("estimation", "Back-of-envelope estimation"), ("api-design", "API design"), ("load-balancing", "Load balancing"),
    ("caching", "Caching strategies"), ("db-choice", "Choosing a database"), ("replication", "Replication & failover"), ("sharding", "Sharding & partitioning"),
    ("cap-consistency", "CAP & consistency models"), ("consistent-hashing", "Consistent hashing"), ("message-queues", "Message queues & delivery guarantees"), ("cdn", "CDN & edge caching"),
    ("object-storage", "Object storage for blobs"), ("rate-limiting", "Rate limiting"), ("id-generation", "Unique ID generation"), ("fanout-feed", "Feed fan-out"),
    ("websockets-realtime", "Real-time delivery"), ("search-indexing", "Search indexing"), ("availability-spof", "Availability & failure handling"), ("idempotency-payments", "Idempotency & payments"),
    ("hot-keys-celebrity", "Hot keys"), ("geospatial", "Geospatial indexing"), ("observability", "Observability & SLOs"),
]
PER_DAY = {"entry": 2, "mid": 2, "senior": 2}
MOCK_EVERY = 7


def _target(db: Session, target: str) -> tuple[list[int], str]:
    if target in TIER_LABELS:
        ids = list(db.scalars(select(Company.id).where(Company.tier == target)))
        return ids, TIER_LABELS[target]
    co = db.scalar(select(Company).where(Company.slug == target))
    if co is None:
        raise ValueError("Unknown target: use a tier id or a company slug")
    return [co.id], co.name


def _candidates(db: Session, company_ids: list[int]) -> list[dict]:
    if not company_ids:
        return []
    rows = db.execute(select(Problem.id, Problem.name, Problem.url, Problem.source_difficulty, Problem.tags, func.count(CompanyProblem.id), func.avg(CompanyProblem.frequency))
                      .join(CompanyProblem, CompanyProblem.problem_id == Problem.id).where(CompanyProblem.company_id.in_(company_ids)).group_by(Problem.id)).all()
    return [{"id": i, "name": n, "url": u, "difficulty": d, "tags": t or [], "companies": c, "freq": float(f or 0)} for i, n, u, d, t, c, f in rows]


def _mix(level: str) -> dict[str, float]:
    return {"entry": {"Easy": 0.45, "Medium": 0.5, "Hard": 0.05}, "mid": {"Easy": 0.2, "Medium": 0.65, "Hard": 0.15}, "senior": {"Easy": 0.1, "Medium": 0.6, "Hard": 0.3}}[level]


def pick_problems(cands: list[dict], tags: list[str], n: int, level: str, solved: set[int], used: set[int]) -> list[dict]:
    """Highest-value unsolved problems for a topic: most companies first, then reported frequency, shaped to the level's difficulty mix, easy->hard ramp."""
    tagset = {t.lower() for t in tags}
    pool = [c for c in cands if c["id"] not in solved and c["id"] not in used and tagset & {t.lower() for t in c["tags"]} and c["difficulty"] in ("Easy", "Medium", "Hard")]
    pool.sort(key=lambda c: (-c["companies"], -c["freq"], c["name"]))
    mix, out = _mix(level), []
    want = {d: round(n * w) for d, w in mix.items()}
    while sum(want.values()) < n:
        want["Medium"] += 1
    while sum(want.values()) > n:
        want[max(want, key=want.get)] -= 1
    for d in ("Easy", "Medium", "Hard"):
        out += [c for c in pool if c["difficulty"] == d][:want[d]]
    if len(out) < n:  # not enough of some difficulty: fill with the best remaining of any
        rest = [c for c in pool if c not in out]
        out += rest[:n - len(out)]
    out.sort(key=lambda c: ("Easy", "Medium", "Hard").index(c["difficulty"]))
    return out[:n]


def _questions(db: Session, level: str, company_domain: str | None, n: int, include_lld: bool) -> list[DesignQuestion]:
    design_questions.seed(db) if not db.scalar(select(func.count(DesignQuestion.id))) else None
    allowed = {"entry": ("entry", "mid"), "mid": ("mid", "senior", "entry"), "senior": ("senior", "mid")}[level]
    qs = [q for q in db.scalars(select(DesignQuestion).order_by(DesignQuestion.id)) if q.kind == "hld" and q.level in allowed[:2 if level != "mid" else 3]]
    pref = {"entry": ["entry", "mid"], "mid": ["mid", "senior", "entry"], "senior": ["senior", "mid"]}[level]
    qs.sort(key=lambda q: (0 if company_domain and company_domain in (q.domains or []) else 1, pref.index(q.level) if q.level in pref else 9, q.id))
    out, seen_cat = [], {}
    for q in qs:  # diversity: at most 2 per category until we run out
        if seen_cat.get(q.category, 0) < 2:
            out.append(q); seen_cat[q.category] = seen_cat.get(q.category, 0) + 1
    out = out[:n]
    if include_lld:
        lld = [q for q in db.scalars(select(DesignQuestion).where(DesignQuestion.kind == "lld").order_by(DesignQuestion.id)) if q.level in ("entry", "mid")][:3]
        out = out[:max(0, n - len(lld))] + lld
    return out


def build(db: Session, user_id: int, days: int, track: str, level: str, target: str, hours: float, start: date | None = None) -> dict:
    if days not in (30, 60) or track not in ("both", "dsa", "sd") or level not in ("entry", "mid", "senior") or not 0.5 <= hours <= 8:
        raise ValueError("days must be 30 or 60; track both|dsa|sd; level entry|mid|senior; hours 0.5-8")
    cids, label = _target(db, target)
    cands = _candidates(db, cids)
    if track != "sd" and not cands:
        raise ValueError("No company data is loaded for that target yet. An admin must run the company-list ingest first.")
    solved = set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == user_id, ProblemStatus.solved.is_(True))))
    domain = db.scalar(select(Company.domain).where(Company.slug == target)) if target not in TIER_LABELS else None
    plan: list[dict] = [{"day": d, "theme": "", "tasks": []} for d in range(1, days + 1)]
    mock_days = {d for d in range(MOCK_EVERY, days + 1, MOCK_EVERY)} | {days}
    work_days = [d for d in range(1, days + 1) if d not in mock_days]
    final_mixed = work_days[-3:] if days >= 30 else []
    study_days = [d for d in work_days if d not in final_mixed]
    n = lambda d, k: f"d{d}:t{k}"

    # ---- DSA: split study days across topics by weight (a topic the student mostly solved already gets half time)
    dsa_days = study_days if track != "sd" else []
    used: set[int] = set()
    if dsa_days:
        weights = []
        for tid, title, tags, w in DSA_TOPICS:
            tagset = {t.lower() for t in tags}
            topic_ids = [c["id"] for c in cands if tagset & {t.lower() for t in c["tags"]}]
            done_frac = (sum(1 for i in topic_ids if i in solved) / len(topic_ids)) if topic_ids else 0
            weights.append((tid, title, tags, w * (0.5 if done_frac >= 0.7 else 1.0) * (1.0 if topic_ids else 0.0), done_frac))
        total = sum(w for *_, w, _ in weights) or 1
        alloc = []
        for tid, title, tags, w, frac in weights:
            k = max(1, round(len(dsa_days) * w / total)) if w > 0 else 0
            alloc.append([tid, title, tags, k, frac])
        while sum(a[3] for a in alloc) > len(dsa_days):  # trim the largest allocation
            max(alloc, key=lambda a: a[3])[3] -= 1
        while sum(a[3] for a in alloc) < len(dsa_days):
            max((a for a in alloc if a[3] > 0), key=lambda a: a[3])[3] += 1
        per_day = max(2, min(5, round(hours * (1.0 if track == "both" else 1.6))))
        it = iter(dsa_days)
        for tid, title, tags, k, frac in alloc:
            for j in range(k):
                d = next(it)
                probs = pick_problems(cands, tags, per_day, level, solved, used)
                used |= {p["id"] for p in probs}
                tasks = plan[d - 1]["tasks"]
                tasks.append({"id": n(d, len(tasks)), "kind": "learn", "title": f"Learn: {title}" + (f" (part {j + 1}/{k})" if k > 1 else ""), "href": f"/mentor?ask={title}", "est_min": 20, "note": "Ask the mentor for the pattern, then solve."})
                for p in probs:
                    tasks.append({"id": n(d, len(tasks)), "kind": "problem", "title": p["name"].strip(), "url": p["url"], "problem_id": p["id"], "difficulty": p["difficulty"], "est_min": {"Easy": 20, "Medium": 35, "Hard": 55}[p["difficulty"]],
                                  "note": f"Reported by {p['companies']} of the target companies"})
                plan[d - 1]["theme"] = "DSA: " + title
    # ---- System design: concepts first, then library questions
    if track != "dsa":
        sd_days = study_days if track == "sd" else [d for d in study_days if d >= 2]
        n_concepts = min(len(SD_CONCEPTS), max(6, round(len(sd_days) * 0.5)))
        n_questions = max(0, len(sd_days) - n_concepts)
        qs = _questions(db, level, domain, n_questions, include_lld=(level == "entry" and days >= 60))
        for i, d in enumerate(sd_days):
            tasks = plan[d - 1]["tasks"]
            if i < n_concepts:
                slug, title = SD_CONCEPTS[i]
                tasks.append({"id": n(d, len(tasks)), "kind": "learn", "title": f"System design concept: {title}", "href": f"/mentor?ask=Teach me {title} for system design interviews", "est_min": 30, "note": "Read the mentor's explanation, then summarise it in 5 lines."})
            elif i - n_concepts < len(qs):
                q = qs[i - n_concepts]
                tasks.append({"id": n(d, len(tasks)), "kind": "design", "title": f"Design: {q.title}", "href": f"/design?question={q.slug}", "question": q.slug, "est_min": 60, "note": "Draw it, write the HLD sections, then get the mentor review."})
            if not plan[d - 1]["theme"]:
                plan[d - 1]["theme"] = "System design"
            elif tasks:
                plan[d - 1]["theme"] += " + system design"
    # ---- final mixed days: highest-value unsolved problems for the target, any topic
    for d in final_mixed:
        if track != "sd":
            probs = pick_problems(cands, [t for _, _, tg, _ in DSA_TOPICS for t in tg], max(3, round(hours * 1.5)), level, solved, used)
            used |= {p["id"] for p in probs}
            for p in probs:
                plan[d - 1]["tasks"].append({"id": n(d, len(plan[d - 1]["tasks"])), "kind": "problem", "title": p["name"], "url": p["url"], "problem_id": p["id"], "difficulty": p["difficulty"], "est_min": 35, "note": f"Mixed practice (reported by {p['companies']} target companies)"})
        plan[d - 1]["tasks"].append({"id": n(d, len(plan[d - 1]["tasks"])), "kind": "review", "title": "Revision centre: clear what is due", "href": "/revision", "est_min": 20, "note": "Spaced repetition of what you struggled with."})
        plan[d - 1]["theme"] = "Mixed practice & revision"
    # ---- mock / review days
    for d in sorted(mock_days):
        t = plan[d - 1]["tasks"]
        t.append({"id": n(d, len(t)), "kind": "review", "title": "Review mistakes and revision", "href": "/mistakes", "est_min": 30, "note": "Re-solve what you failed this week."})
        if track != "sd":
            t.append({"id": n(d, len(t)), "kind": "mock", "title": "Timed mock coding interview", "href": "/interview", "est_min": 45, "note": "Think aloud; the interviewer scores your reasoning."})
        if track != "dsa":
            t.append({"id": n(d, len(t)), "kind": "design", "title": "Timed system design (45 min) on a question you have not seen", "href": "/design", "est_min": 45, "note": "Pick any question from the library and design it in one sitting."})
        plan[d - 1]["theme"] = "Mock & review" if d != days else "Final mock & review"
    for p in plan:
        p["minutes"] = sum(t["est_min"] for t in p["tasks"])
    return {"plan": plan, "target_label": label, "summary": {"dsa_problems": sum(1 for p in plan for t in p["tasks"] if t["kind"] == "problem"), "design_tasks": sum(1 for p in plan for t in p["tasks"] if t["kind"] == "design"),
                                                          "mocks": sum(1 for p in plan for t in p["tasks"] if t["kind"] == "mock")}}


def create(db: Session, user_id: int, days: int, track: str, level: str, target: str, hours: float, start: date | None = None) -> CrashCourse:
    built = build(db, user_id, days, track, level, target, hours, start)
    for c in db.scalars(select(CrashCourse).where(CrashCourse.user_id == user_id, CrashCourse.active.is_(True))):
        c.active = False
    cc = CrashCourse(user_id=user_id, days=days, track=track, level=level, target=target, hours=hours, started_on=(start or date.today()).isoformat(), plan=built["plan"], done=[], active=True)
    db.add(cc); db.commit()
    return cc


def view(db: Session, cc: CrashCourse, today: date | None = None) -> dict:
    today = today or date.today()
    start = date.fromisoformat(cc.started_on)
    day_no = (today - start).days + 1
    solved = set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == cc.user_id, ProblemStatus.solved.is_(True))))
    done = set(cc.done or [])
    total = completed = 0
    days = []
    for p in cc.plan:
        tasks = []
        for t in p["tasks"]:
            auto = t["kind"] == "problem" and t.get("problem_id") in solved
            ok = t["id"] in done or auto
            total += 1; completed += ok
            tasks.append({**t, "done": ok, "auto": auto and t["id"] not in done})
        days.append({**p, "tasks": tasks, "date": (start + timedelta(days=p["day"] - 1)).isoformat(), "complete": bool(tasks) and all(x["done"] for x in tasks)})
    overdue = [{"day": d["day"], **t} for d in days if d["day"] < day_no for t in d["tasks"] if not t["done"]]
    streak = 0
    for d in reversed([d for d in days if d["day"] <= min(day_no, cc.days)]):
        if d["complete"]:
            streak += 1
        elif d["day"] == day_no:
            continue
        else:
            break
    return {"id": cc.id, "days": cc.days, "track": cc.track, "level": cc.level, "target": cc.target, "hours": cc.hours, "started_on": cc.started_on, "day_number": day_no,
            "status": "not_started" if day_no < 1 else "finished" if day_no > cc.days else "running", "progress": {"done": completed, "total": total, "ratio": round(completed / total, 3) if total else 0},
            "summary": {"dsa_problems": sum(1 for p in cc.plan for t in p["tasks"] if t["kind"] == "problem"), "design_tasks": sum(1 for p in cc.plan for t in p["tasks"] if t["kind"] == "design"),
                        "mocks": sum(1 for p in cc.plan for t in p["tasks"] if t["kind"] == "mock")},
            "streak_days": streak, "overdue_count": len(overdue), "overdue": overdue[:30], "plan": days,
            "note": "A schedule, not a prediction. Problems are the ones target companies are reported to ask (community-reported data); 'done' is auto-ticked when your synced submissions show a solve."}
