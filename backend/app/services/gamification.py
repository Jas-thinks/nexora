"""Gamification from real events only. Rules are explicit and anti-farming: XP is awarded once per problem (first AC), imported/self-reported
solves earn half, and nothing is awarded for time spent or messages sent. Leaderboards are opt-in and rank weekly XP (never ratings)."""
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import UserPrefs
from app.models.catalog import Problem, ProblemStatus
from app.models.daily import DailyChallenge
from app.models.integrations import RatingHistory, Submission
from app.models.user import User
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID

TIER_XP = {1: 10, 2: 25, 3: 60, None: 10}
RULES = {"first_ac": "10 / 25 / 60 XP for an easy / medium / hard first accepted solve (unrated = 10). Once per problem.",
         "unverified": "Imported or self-reported solves earn 50% (they cannot be checked).",
         "daily": "+20 XP for completing the Daily Challenge, +10 if solved without reading the editorial.",
         "revision": "+15 XP for completing a revision challenge.",
         "streak": "+1 XP per streak day per active day, up to 7 (so long streaks add a small, capped bonus)."}


def level_for(xp: int) -> tuple[int, int, int]:
    """-> (level, xp_into_level, xp_needed_for_next). Level n needs 100*n^1.4 cumulative XP (smooth, no cliffs)."""
    lvl = 1
    while xp >= round(100 * lvl ** 1.4):
        lvl += 1
    prev = round(100 * (lvl - 1) ** 1.4) if lvl > 1 else 0
    return lvl, xp - prev, round(100 * lvl ** 1.4) - prev


def _aw(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def xp_events(db: Session, user_id: int) -> list[dict]:
    """Every XP award with date, amount and reason. Deterministic; recomputed from stored events (no stored counters to drift)."""
    ev: list[dict] = []
    first_ac: dict[int, tuple[datetime, bool]] = {}
    days: set[date] = set()
    for pid, v, at, prov in db.execute(select(Submission.problem_id, Submission.verdict, Submission.submitted_at, Submission.provenance)
                                       .where(Submission.user_id == user_id).order_by(Submission.submitted_at)):
        at = _aw(at); days.add(at.date())
        if v == "AC" and pid and pid not in first_ac:
            first_ac[pid] = (at, prov == "verified")
    for st in db.scalars(select(ProblemStatus).where(ProblemStatus.user_id == user_id, ProblemStatus.solved.is_(True))):
        if st.problem_id not in first_ac:  # self-reported: half value, dated by when it was reported
            first_ac[st.problem_id] = (_aw(st.updated_at), False)
            days.add(_aw(st.updated_at).date())
    probs = {}
    ids = list(first_ac)
    for i in range(0, len(ids), 900):
        probs.update({p.id: p for p in db.scalars(select(Problem).where(Problem.id.in_(ids[i:i + 900])))})
    for pid, (at, verified) in first_ac.items():
        p = probs.get(pid)
        base = TIER_XP[mastery.tier(p) if p else None]
        ev.append({"at": at, "xp": base if verified else base // 2, "reason": f"first solve: {p.name if p else pid}" + ("" if verified else " (unverified, 50%)")})
    for ch in db.scalars(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.status == "completed")):
        fb = ch.feedback or {}
        at = _aw(ch.completed_at or ch.created_at)
        if ch.mode == "revision":
            ev.append({"at": at, "xp": 15, "reason": "revision completed"})
        else:
            ev.append({"at": at, "xp": 20 + (10 if fb.get("solved") and not fb.get("editorial_viewed") else 0), "reason": "daily challenge completed"})
    run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and (d - prev).days == 1 else 1
        prev = d
        if run > 1:
            ev.append({"at": datetime.combine(d, datetime.min.time(), UTC) + timedelta(hours=23), "xp": min(run, 7), "reason": f"streak day {run}"})
    ev.sort(key=lambda e: e["at"])
    return ev


def badges(db: Session, user_id: int, ev: list[dict]) -> list[dict]:
    from app.services.student_analytics import _streaks
    subs = list(db.execute(select(Submission.problem_id, Submission.verdict, Submission.submitted_at).where(Submission.user_id == user_id).order_by(Submission.submitted_at)))
    days = {_aw(s[2]).date() for s in subs}
    _, longest = _streaks(days, datetime.now(UTC).date()) if days else (0, 0)
    solved = {s[0] for s in subs if s[1] == "AC" and s[0]}
    states = mastery.assess_cached(db, user_id)
    mastered = [s for s in states.values() if s.status == "mastered"]
    pmap = mastery.problem_patterns(db)
    pats = {x for pid in solved for x in pmap.get(pid, [])}
    hard = 0
    if solved:
        hard = sum(1 for p in db.scalars(select(Problem).where(Problem.id.in_(list(solved)[:5000]))) if mastery.tier(p) == 3)
    ds = sorted(days)
    comeback = any((b - a).days >= 14 for a, b in zip(ds, ds[1:]))
    rev = db.scalars(select(DailyChallenge).where(DailyChallenge.user_id == user_id, DailyChallenge.mode == "revision", DailyChallenge.status == "completed")).all()
    rh = list(db.scalars(select(RatingHistory).where(RatingHistory.user_id == user_id).order_by(RatingHistory.at)))
    climb = 0
    for pl in {r.platform for r in rh}:
        rr = [r.new_rating for r in rh if r.platform == pl and r.new_rating]
        for i in range(len(rr)):
            climb = max(climb, rr[min(i + 5, len(rr) - 1)] - rr[i])  # best gain over any window of up to 5 contests
    def b(id_, name, desc, have, goal, evidence):
        return {"id": id_, "name": name, "description": desc, "earned": have >= goal, "progress": min(have, goal), "goal": goal, "evidence": evidence if have >= goal else None}
    return [
        b("first-solve", "First Blood", "Your first accepted solution.", len(solved), 1, f"{len(solved)} problems solved"),
        b("streak-3", "On a Roll", "3 active days in a row.", longest, 3, f"longest streak {longest}"),
        b("streak-7", "Week Warrior", "7 active days in a row.", longest, 7, f"longest streak {longest}"),
        b("streak-30", "Unstoppable", "30 active days in a row.", longest, 30, f"longest streak {longest}"),
        b("century", "Century", "100 distinct problems solved.", len(solved), 100, f"{len(solved)} solved"),
        b("explorer", "Pattern Explorer", "Solved problems in 5 different patterns.", len(pats), 5, f"{len(pats)} patterns"),
        b("master", "Pattern Master", "Reached 'mastered' in a pattern (multi-signal, not a solve count).", len(mastered), 1, ", ".join(BY_ID[s.pattern].name for s in mastered[:3])),
        b("hard-hitter", "Hard Hitter", "Solved 5 hard-tier problems.", hard, 5, f"{hard} hard solves"),
        b("comeback", "Comeback", "Returned after 14+ days away.", 1 if comeback else 0, 1, "returned after a break"),
        b("revision-keeper", "Revision Keeper", "Completed 5 revision challenges.", len(rev), 5, f"{len(rev)} revisions"),
        b("climber", "Contest Climber", "Gained 100+ rating over 5 contests.", climb, 100, f"+{climb} over 5 contests"),
    ]


def weekly_challenge(db: Session, user_id: int, today: date) -> dict | None:
    """Personalised: strengthen the weakest MEASURABLE pattern whose prerequisites are fine. Progress = distinct problems solved this ISO week in that pattern."""
    from app.patterns.mapping import observable_patterns
    states = mastery.assess_cached(db, user_id)
    cands = sorted((s for s in states.values() if s.status in ("weak", "learning", "practised") and s.attempted > 0), key=lambda s: (s.score, s.pattern))
    if not cands:
        return None
    s = cands[0]
    redirected_from = None
    if s.missing_prereqs:  # firm up a measurable prerequisite first instead of pushing a pattern the student isn't ready for
        pre = next((q for q in s.missing_prereqs if q in observable_patterns()), None)
        if pre:
            redirected_from, s = s, states[pre]
    monday = today - timedelta(days=today.weekday())
    pmap = mastery.problem_patterns(db)
    week_start = datetime.combine(monday, datetime.min.time(), UTC)
    done = {pid for pid, at in db.execute(select(Submission.problem_id, Submission.submitted_at).where(Submission.user_id == user_id, Submission.verdict == "AC", Submission.problem_id.is_not(None)))
            if _aw(at) >= week_start and s.pattern in pmap.get(pid, [])}
    target = 2
    return {"pattern": s.pattern, "name": BY_ID[s.pattern].name, "status": s.status, "mastery_score": s.score, "target": target, "progress": min(len(done), target),
            "week_of": monday.isoformat(), "prerequisite_for": BY_ID[redirected_from.pattern].name if redirected_from else None,
            "text": (f"{BY_ID[redirected_from.pattern].name} is your weakest area (score {redirected_from.score:.2f}), but its prerequisite {BY_ID[s.pattern].name} is not solid yet ({s.status}). " if redirected_from else
                     f"Your {BY_ID[s.pattern].name} mastery score is {s.score:.2f} ({s.status}). ") + f"Solve {target} {BY_ID[s.pattern].name} problems this week to strengthen it."}


def goals(db: Session, user_id: int, ev: list[dict], prefs: UserPrefs | None, today: date) -> dict:
    d, w = (prefs.daily_goal if prefs else 1), (prefs.weekly_goal if prefs else 5)
    first = [e for e in ev if e["reason"].startswith("first solve")]
    monday = today - timedelta(days=today.weekday())
    return {"daily": {"target": d, "progress": sum(1 for e in first if e["at"].date() == today)},
            "weekly": {"target": w, "progress": sum(1 for e in first if e["at"].date() >= monday)}}


def streak_info(db: Session, user_id: int, today: date) -> dict:
    from app.services.student_analytics import _streaks
    days = {_aw(a).date() for (a,) in db.execute(select(Submission.submitted_at).where(Submission.user_id == user_id))}
    cur, longest = _streaks(days, today) if days else (0, 0)
    return {"current": cur, "longest": longest, "active_today": today in days}


def profile(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or datetime.now(UTC).date()
    ev = xp_events(db, user_id)
    xp = sum(e["xp"] for e in ev)
    lvl, into, need = level_for(xp)
    prefs = db.get(UserPrefs, user_id)
    bs = badges(db, user_id, ev)
    monday = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time(), UTC)
    return {"streak": streak_info(db, user_id, today), "xp": xp, "level": lvl, "level_progress": into, "level_needed": need, "weekly_xp": sum(e["xp"] for e in ev if e["at"] >= monday),
            "goals": goals(db, user_id, ev, prefs, today), "badges": bs, "badges_earned": sum(1 for x in bs if x["earned"]),
            "weekly_challenge": weekly_challenge(db, user_id, today), "recent": [{"at": e["at"], "xp": e["xp"], "reason": e["reason"]} for e in ev[-8:]][::-1],
            "rules": RULES, "leaderboard_visible": bool(prefs and prefs.leaderboard_visible)}


def leaderboard(db: Session, me: int, today: date | None = None, limit: int = 10) -> dict:
    today = today or datetime.now(UTC).date()
    monday = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time(), UTC)
    rows = []
    for p in db.scalars(select(UserPrefs).where(UserPrefs.leaderboard_visible.is_(True))):
        u = db.get(User, p.user_id)
        if u is None or not u.is_active:
            continue
        w = sum(e["xp"] for e in xp_events(db, u.id) if e["at"] >= monday)
        rows.append({"user_id": u.id, "name": u.display_name, "weekly_xp": w})
    rows.sort(key=lambda r: (-r["weekly_xp"], r["user_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    mine = next((r for r in rows if r["user_id"] == me), None)
    return {"week_of": monday.date().isoformat(), "entries": [{"rank": r["rank"], "name": r["name"], "weekly_xp": r["weekly_xp"], "you": r["user_id"] == me} for r in rows[:limit]],
            "you": None if mine is None else {"rank": mine["rank"], "weekly_xp": mine["weekly_xp"]}, "participants": len(rows),
            "note": "Opt-in only. Ranks weekly XP from verified activity; ratings are never compared."}
