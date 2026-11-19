"""Goal planner: 'reach rating X by date D'. Rebuilt from live data on every call, so it adapts weekly. Never promises an outcome:
feasibility compares the target with the student's own historical pace and states its assumptions."""
import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import Goal
from app.models.integrations import RatingHistory, Submission
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID


def _aw(d):
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def set_goal(db: Session, user_id: int, target: int, deadline: datetime, platform: str = "codeforces") -> Goal:
    now = datetime.now(UTC)
    if not 800 <= target <= 4000:
        raise ValueError("target must be between 800 and 4000")
    if deadline <= now + timedelta(days=7) or deadline > now + timedelta(days=730):
        raise ValueError("deadline must be between 1 week and 2 years from now")
    g = db.scalar(select(Goal).where(Goal.user_id == user_id)) or Goal(user_id=user_id, platform=platform, target=target, deadline=deadline)
    g.platform, g.target, g.deadline = platform, target, deadline
    db.add(g); db.commit()
    return g


def plan(db: Session, user_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    g = db.scalar(select(Goal).where(Goal.user_id == user_id))
    if g is None:
        return {"goal": None, "message": "Set a target to get a plan."}
    weeks = max(1, math.ceil((_aw(g.deadline) - now).days / 7))
    rh = list(db.scalars(select(RatingHistory).where(RatingHistory.user_id == user_id, RatingHistory.platform == g.platform).order_by(RatingHistory.at)))
    est, conf = mastery.estimate_cached(db, user_id)
    current = rh[-1].new_rating if rh and rh[-1].new_rating else est
    src = f"latest {g.platform} rating" if rh and rh[-1].new_rating else f"estimate from solved problems (confidence {conf})"
    gain = g.target - current
    recent = [r for r in rh if _aw(r.at) >= now - timedelta(days=180) and r.new_rating is not None]
    pace = None
    if len(recent) >= 5:
        span_w = max(1.0, (_aw(recent[-1].at) - _aw(recent[0].at)).days / 7)
        pace = round((recent[-1].new_rating - recent[0].new_rating) / span_w, 2)
    ac_days = [(_aw(a)).date() for (a,) in db.execute(select(Submission.submitted_at).where(Submission.user_id == user_id, Submission.verdict == "AC", Submission.provenance == "verified",
                                                                                              Submission.submitted_at >= now - timedelta(days=56)))]
    velocity = round(len(ac_days) / 8, 1)
    if gain <= 0:
        verdict, why = "already_met", f"Your {src} ({current}) already meets the target {g.target}."
    elif pace is None:
        verdict, why = "insufficient_data", "Fewer than 5 rated contests in the last 180 days, so Nexora cannot project your pace. The plan below is a structured schedule, not a forecast."
    else:
        proj = current + pace * weeks
        verdict = "on_track" if proj >= g.target else "behind"
        why = f"At your own pace over the last 180 days ({pace:+g} rating/week) you would reach ≈{round(proj)} in {weeks} weeks; target {g.target}. Ratings are noisy: treat as a rough guide."
    states = mastery.assess_cached(db, user_id)
    weak = [s for s in sorted(states.values(), key=lambda s: s.score) if s.status in ("weak", "learning", "unexplored") and not s.missing_prereqs and s.pattern in mastery.observable_patterns()]
    quota = int(min(25, max(3, math.ceil(max(velocity, 2) * 1.25))))
    wk = []
    for i in range(min(weeks, 12)):
        foc = weak[i * 2:i * 2 + 2] or weak[:2]
        lo = int(current + gain * i / max(1, weeks) - 100) if gain > 0 else current - 100
        wk.append({"week": i + 1, "starts": (now + timedelta(days=7 * i)).date().isoformat(), "focus_patterns": [{"id": s.pattern, "name": BY_ID[s.pattern].name, "status": s.status} for s in foc],
                   "problem_quota": quota, "rating_band": [max(800, lo), max(900, lo + 300)], "milestone_rating": int(current + gain * (i + 1) / max(1, weeks)) if gain > 0 else current,
                   "also": "Do the Daily Challenge and clear due revisions." if i % 2 == 0 else "Take part in one rated contest and upsolve it."})
    return {"goal": {"platform": g.platform, "target": g.target, "deadline": _aw(g.deadline).date().isoformat(), "weeks_left": weeks}, "current": {"rating": current, "source": src}, "gain_needed": gain,
            "feasibility": {"verdict": verdict, "explanation": why, "pace_per_week": pace, "solve_velocity_per_week": velocity},
            "weeks": wk, "assumptions": ["Weekly quota = 1.25 × your verified solve rate over the last 8 weeks (min 3, max 25).", "Focus patterns are your weakest measurable patterns with satisfied prerequisites.",
                                         "Milestone ratings are evenly spaced waypoints, not predictions.", "The plan is recomputed from your latest data each time you open it."]}
