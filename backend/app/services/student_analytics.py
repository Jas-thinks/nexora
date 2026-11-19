"""Student analytics from the student's OWN persisted events. Every metric carries a definition and source; unknown is None, never 0."""
import statistics
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Problem
from app.models.daily import DailyChallenge, ReviewItem
from app.models.integrations import ConnectedProfile, RatingHistory, Submission
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID

RANGES = {"30d": 30, "90d": 90, "180d": 180, "365d": 365, "all": None}
DEFS = {
    "acceptance_rate": ("AC submissions / all submissions in range", "submissions"),
    "solved": ("Distinct problems with at least one AC in range (first AC falls in range)", "submissions + progress"),
    "consistency": ("Active days / days in range (a day is active if it has >=1 submission)", "submissions"),
    "streak": ("Consecutive active days ending today (or yesterday)", "submissions"),
    "first_try_rate": ("Distinct problems whose FIRST submission was AC / distinct problems attempted — proxy for solving unfamiliar problems", "submissions"),
    "difficulty_trend": ("Mean rating of newly solved rated problems per week (rated problems only)", "submissions + catalog"),
    "improvement": ("Second half of range vs first half; reported only with >= 10 submissions in each half", "submissions"),
    "abandoned": ("Attempted >= 3 times, never solved, last attempt > 14 days ago", "submissions"),
}


def _aw(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _week(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def _streaks(days: set[date], today: date) -> tuple[int, int]:
    cur = 0
    d = today if today in days else today - timedelta(days=1)
    while d in days:
        cur += 1; d -= timedelta(days=1)
    longest = run = 0
    prev = None
    for x in sorted(days):
        run = run + 1 if prev and (x - prev).days == 1 else 1
        longest = max(longest, run); prev = x
    return cur, longest


def _half(subs):
    ac = sum(1 for s in subs if s[1] == "AC")
    return {"n": len(subs), "acceptance": round(ac / len(subs), 3) if subs else None}


def compute(db: Session, user_id: int, rng: str = "90d", now: datetime | None = None) -> dict:
    if rng not in RANGES:
        raise ValueError(f"range must be one of {list(RANGES)}")
    now = now or datetime.now(UTC)
    today = now.date()
    days = RANGES[rng]
    start = None if days is None else today - timedelta(days=days - 1)

    rows = db.execute(select(Submission.problem_id, Submission.verdict, Submission.submitted_at, Submission.language, Submission.platform,
                             Submission.provenance, Submission.in_contest, Submission.problem_ref)
                      .where(Submission.user_id == user_id).order_by(Submission.submitted_at)).all()
    all_subs = [(r[0], r[1], _aw(r[2]), r[3], r[4], r[5], r[6], r[7]) for r in rows]
    if start is None and all_subs:
        start = all_subs[0][2].date()
    subs = [s for s in all_subs if start is None or s[2].date() >= start]
    span = max(1, (today - start).days + 1) if start else 0
    probs = {}
    pids = {s[0] for s in all_subs if s[0]}
    ids = list(pids)
    for i in range(0, len(ids), 900):
        probs.update({p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(ids[i:i + 900])))})

    out: dict = {"range": rng, "from": start.isoformat() if start else None, "to": today.isoformat(), "definitions": {k: {"definition": d, "source": s} for k, (d, s) in DEFS.items()}}
    prof = list(db.scalars(select(ConnectedProfile).where(ConnectedProfile.user_id == user_id)))
    out["freshness"] = {"profiles": [{"platform": p.platform, "handle": p.handle, "data_level": p.data_level, "last_synced_at": p.last_synced_at} for p in prof],
                        "note": "Only data from linked/imported sources is analysed. Platforms without verified history show nothing, not zero."}
    if not all_subs:
        out["empty"] = True
        out["message"] = "No submissions yet. Link a platform (Platforms page) or import a CSV to unlock analytics."
        out["summary"] = {k: None for k in ("submissions", "accepted", "acceptance_rate", "solved", "active_days", "consistency", "streak", "longest_streak", "first_try_rate")}
        out["next_best_action"] = [{"action": "Connect a platform", "why": "Analytics need your submission history.", "href": "/connections"}]
        return out

    # ---- summary
    ac = [s for s in subs if s[1] == "AC"]
    active = {s[2].date() for s in subs}
    cur, longest = _streaks({s[2].date() for s in all_subs}, today)
    first_ac_by_pid: dict = {}
    first_sub_by_pid: dict = {}
    attempts_by_pid: Counter = Counter()
    last_by_pid: dict = {}
    for pid, v, at, *_ in all_subs:
        key = pid if pid else None
        if key is None:
            continue
        first_sub_by_pid.setdefault(pid, v)
        attempts_by_pid[pid] += 1
        last_by_pid[pid] = at
        if v == "AC":
            first_ac_by_pid.setdefault(pid, at)
    solved_in_range = {p for p, at in first_ac_by_pid.items() if start is None or at.date() >= start}
    attempted = set(first_sub_by_pid)
    first_try = sum(1 for p in attempted if first_sub_by_pid[p] == "AC")
    out["summary"] = {
        "submissions": len(subs), "accepted": len(ac), "acceptance_rate": round(len(ac) / len(subs), 3) if subs else None,
        "solved": len(solved_in_range), "solved_all_time": len(first_ac_by_pid), "attempted_problems_all_time": len(attempted),
        "active_days": len(active), "consistency": round(len(active) / span, 3) if span else None, "streak": cur, "longest_streak": longest,
        "first_try_rate": round(first_try / len(attempted), 3) if attempted else None,
        "unlinked_submissions": sum(1 for s in subs if not s[0]), "imported_submissions": sum(1 for s in subs if s[5] != "verified"),
    }

    # ---- heatmap (last 365 days, independent of selected range)
    hm_start = today - timedelta(days=364)
    hm: dict = defaultdict(lambda: [0, 0])
    for s in all_subs:
        d = s[2].date()
        if d >= hm_start:
            hm[d.isoformat()][0] += 1; hm[d.isoformat()][1] += s[1] == "AC"
    out["heatmap"] = [{"date": d, "submissions": v[0], "accepted": v[1]} for d, v in sorted(hm.items())]

    # ---- weekly timeline
    wk: dict = defaultdict(lambda: {"submissions": 0, "accepted": 0, "ratings": [], "solved": 0})
    for s in subs:
        w = wk[_week(s[2].date())]; w["submissions"] += 1; w["accepted"] += s[1] == "AC"
    for pid, at in first_ac_by_pid.items():
        if start is None or at.date() >= start:
            w = wk[_week(at.date())]; w["solved"] += 1
            p = probs.get(pid)
            if p and p.rating:
                w["ratings"].append(p.rating)
    out["weekly"] = [{"week": k, "submissions": v["submissions"], "accepted": v["accepted"], "acceptance": round(v["accepted"] / v["submissions"], 3) if v["submissions"] else None,
                      "solved": v["solved"], "mean_solved_rating": round(sum(v["ratings"]) / len(v["ratings"])) if v["ratings"] else None} for k, v in sorted(wk.items())]

    # ---- distributions
    out["verdicts"] = dict(Counter(s[1] for s in subs).most_common())
    out["languages"] = dict(Counter(s[3] for s in subs if s[3]).most_common(8))
    out["language_unknown"] = sum(1 for s in subs if not s[3])
    out["platforms"] = dict(Counter(s[4] for s in subs).most_common())
    tiers = Counter()
    bands = Counter()
    for pid in solved_in_range:
        p = probs.get(pid)
        if not p:
            continue
        t = mastery.tier(p)
        tiers[{1: "easy", 2: "medium", 3: "hard", None: "unrated"}[t]] += 1
        if p.rating:
            bands[(p.rating // 200) * 200] += 1
    out["solved_by_tier"] = dict(tiers)
    out["solved_by_rating_band"] = {str(k): v for k, v in sorted(bands.items())}
    out["difficulty_note"] = "Tier uses rating (<1200 easy, <1800 medium) or the source's Easy/Medium/Hard label; unrated problems are listed as 'unrated'."

    # ---- contests / ratings
    rh = list(db.scalars(select(RatingHistory).where(RatingHistory.user_id == user_id).order_by(RatingHistory.at)))
    byp: dict = defaultdict(list)
    for r in rh:
        byp[r.platform].append(r)
    out["ratings"] = {}
    for plat, rs in byp.items():
        news = [r.new_rating for r in rs if r.new_rating is not None]
        deltas = [r.new_rating - r.old_rating for r in rs if r.new_rating is not None and r.old_rating is not None and r.old_rating > 0]
        ranks = [r.rank for r in rs if r.rank]
        perfs = [r.performance for r in rs if r.performance]
        out["ratings"][plat] = {"contests": len(rs), "current": news[-1] if news else None, "peak": max(news) if news else None,
                                "volatility": round(statistics.pstdev(deltas), 1) if len(deltas) >= 3 else None,
                                "last5_change": sum(deltas[-5:]) if deltas else None, "median_rank": statistics.median(ranks) if ranks else None,
                                "median_performance": statistics.median(perfs) if perfs else None,
                                "history": [{"at": r.at.isoformat(), "rating": r.new_rating, "contest": r.contest_name, "rank": r.rank} for r in rs[-400:]]}
    known = [s for s in subs if s[6] is not None]
    out["contest_accuracy"] = None if len(known) < 10 else {
        "in_contest": _half([s for s in known if s[6]]), "practice": _half([s for s in known if not s[6]]),
        "unknown_excluded": len(subs) - len(known)}

    # ---- improvement (halves)
    if len(subs) >= 20:
        mid = subs[len(subs) // 2][2]
        a, b = [s for s in subs if s[2] < mid], [s for s in subs if s[2] >= mid]
        ha, hb = _half(a), _half(b)
        out["improvement"] = {"first_half": ha, "second_half": hb,
                              "acceptance_delta": None if None in (ha["acceptance"], hb["acceptance"]) else round(hb["acceptance"] - ha["acceptance"], 3),
                              "verdict": None, "note": "Descriptive comparison, not causal."}
        d = out["improvement"]["acceptance_delta"]
        out["improvement"]["verdict"] = None if d is None or min(ha["n"], hb["n"]) < 10 else ("improving" if d > 0.03 else "declining" if d < -0.03 else "stable")
    else:
        out["improvement"] = None

    # ---- behaviour
    ab = [p for p, n in attempts_by_pid.items() if n >= 3 and p not in first_ac_by_pid and (today - last_by_pid[p].date()).days > 14]
    out["abandoned"] = {"count": len(ab), "examples": [{"problem_id": p, "name": probs[p].name if p in probs else None, "attempts": attempts_by_pid[p]} for p in ab[:5]]}
    rep = [p for p, n in attempts_by_pid.items() if n >= 3 and p not in first_ac_by_pid and (today - last_by_pid[p].date()).days <= 14]
    out["repeated_failures"] = {"count": len(rep), "examples": [{"problem_id": p, "name": probs[p].name if p in probs else None, "attempts": attempts_by_pid[p]} for p in rep[:5]]}
    ds = sorted({s[2].date() for s in all_subs})
    gaps = sorted(((b - a).days, a.isoformat()) for a, b in zip(ds, ds[1:]) if (b - a).days > 7)[-3:]
    out["inactivity_gaps"] = [{"days": d, "after": a} for d, a in reversed(gaps)]

    # ---- topics: recent vs prior
    recent_cut = today - timedelta(days=30)
    topic = defaultdict(lambda: {"attempted": set(), "solved": set(), "recent": [0, 0], "prior": [0, 0]})
    for pid, v, at, *_ in all_subs:
        p = probs.get(pid) if pid else None
        if not p:
            continue
        for t in p.tags:
            if t == "*special":
                continue
            x = topic[t]; x["attempted"].add(pid)
            if v == "AC": x["solved"].add(pid)
            bucket = x["recent"] if at.date() >= recent_cut else x["prior"]
            bucket[0] += 1; bucket[1] += v == "AC"
    tl = []
    for t, x in topic.items():
        if len(x["attempted"]) < 5:
            continue
        r, pr = x["recent"], x["prior"]
        tl.append({"topic": t, "attempted": len(x["attempted"]), "solved": len(x["solved"]), "acceptance": round(len(x["solved"]) / len(x["attempted"]), 3),
                   "recent_acceptance": round(r[1] / r[0], 3) if r[0] >= 5 else None, "prior_acceptance": round(pr[1] / pr[0], 3) if pr[0] >= 5 else None})
    for x in tl:
        x["trend"] = None if x["recent_acceptance"] is None or x["prior_acceptance"] is None else round(x["recent_acceptance"] - x["prior_acceptance"], 3)
    out["topics"] = {"strongest": sorted(tl, key=lambda x: -x["acceptance"])[:6], "weakest": sorted(tl, key=lambda x: x["acceptance"])[:6],
                     "improving": sorted([x for x in tl if x["trend"] and x["trend"] > 0.05], key=lambda x: -x["trend"])[:5],
                     "stagnating": sorted([x for x in tl if x["trend"] is not None and abs(x["trend"]) <= 0.05 and x["acceptance"] < 0.5], key=lambda x: x["acceptance"])[:5],
                     "note": "Topics with fewer than 5 attempted problems are not scored."}

    # ---- pattern mastery summary + next best actions
    states = mastery.assess_cached(db, user_id)
    cov = mastery.coverage(states)
    weak = sorted((s for s in states.values() if s.status in ("weak", "learning") and not s.missing_prereqs), key=lambda s: s.score)[:3]
    out["patterns"] = {"coverage": cov, "weakest": [{"id": s.pattern, "name": BY_ID[s.pattern].name, "status": s.status, "score": s.score} for s in weak]}
    due = db.scalars(select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.due_at <= now)).all()
    ch = db.scalar(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.day == today, DailyChallenge.status != "swapped"))
    nba = []
    if cur and today not in active and cur > 0:
        nba.append({"action": "Protect your streak", "why": f"{cur}-day streak ends tonight without a submission.", "href": "/daily"})
    if ch is None or ch.status == "assigned":
        nba.append({"action": "Do today's Daily Challenge", "why": "Personalised to your weakest evidence-backed pattern.", "href": "/daily"})
    if due:
        nba.append({"action": f"Review {len(due)} problem(s) due", "why": "Spaced repetition is due; reviews are cheapest right now.", "href": "/daily"})
    if weak:
        nba.append({"action": f"Practise {BY_ID[weak[0].pattern].name}", "why": f"Status {weak[0].status}, score {weak[0].score:.2f}.", "href": f"/patterns/{weak[0].pattern}"})
    if out["abandoned"]["count"]:
        nba.append({"action": "Revisit an abandoned problem", "why": f"{out['abandoned']['count']} problems attempted 3+ times and never solved.", "href": "/explorer"})
    out["next_best_action"] = nba[:4] or [{"action": "Keep going", "why": "No urgent signals.", "href": "/practice"}]
    return out
