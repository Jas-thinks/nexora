
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.ai import UserPrefs
from app.models.catalog import ProblemStatus
from app.models.integrations import RatingHistory
from app.models.user import User
from app.patterns import mastery
from app.patterns.taxonomy import BY_ID
from app.services import gamification

router = APIRouter(tags=["profile"])


@router.get("/profile/{uid}")
def public_profile(uid: int, db: Session = Depends(get_db)):
    """Public (no auth) but ONLY if the user explicitly enabled sharing. Same 404 whether the user is missing or private."""
    pr = db.get(UserPrefs, uid)
    u = db.get(User, uid)
    if u is None or not u.is_active or not (pr and pr.share_progress):
        raise HTTPException(404, "Profile not found")
    g = gamification.profile(db, uid)
    states = mastery.assess_cached(db, uid)
    rh = list(db.scalars(select(RatingHistory).where(RatingHistory.user_id == uid).order_by(RatingHistory.at)))
    ratings = {}
    for r in rh:
        if r.new_rating:
            x = ratings.setdefault(r.platform, {"current": None, "peak": 0, "contests": 0}); x["current"] = r.new_rating; x["peak"] = max(x["peak"], r.new_rating); x["contests"] += 1
    solved = len(set(db.scalars(select(ProblemStatus.problem_id).where(ProblemStatus.user_id == uid, ProblemStatus.solved.is_(True)))))
    return {"name": u.display_name, "member_since": u.created_at, "level": g["level"], "xp": g["xp"], "streak": g["streak"]["current"], "longest_streak": g["streak"]["longest"], "solved": solved,
            "badges": [{"id": b["id"], "name": b["name"]} for b in g["badges"] if b["earned"]], "mastered_patterns": [BY_ID[s.pattern].name for s in states.values() if s.status == "mastered"][:12],
            "ratings": ratings, "note": "Shared by the user. Ratings are as reported by the platforms they connected."}
