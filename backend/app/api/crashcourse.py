from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models.resources import CrashCourse
from app.models.user import User
from app.resources.tiers import TIER_LABELS
from app.services import crashcourse

router = APIRouter(tags=["crash-course"])


class CourseIn(BaseModel):
    days: int = Field(30)
    track: str = Field("both", pattern="^(both|dsa|sd)$")
    level: str = Field("entry", pattern="^(entry|mid|senior)$")
    target: str = Field("service", max_length=80)  # tier id or company slug
    hours: float = Field(2.0, ge=0.5, le=8)


def _active(db: Session, user: User) -> CrashCourse | None:
    return db.scalar(select(CrashCourse).where(CrashCourse.user_id == user.id, CrashCourse.active.is_(True)).order_by(CrashCourse.id.desc()))


@router.get("/planner/crash-course/options")
def options(user: User = Depends(current_user)):
    return {"days": [30, 60], "tracks": {"both": "DSA + system design", "dsa": "DSA only", "sd": "System design only"}, "levels": {"entry": "Entry / fresher (SDE-1)", "mid": "Mid (SDE-2)", "senior": "Senior"},
            "tiers": TIER_LABELS, "hours": [1, 2, 3, 4, 6]}


@router.post("/planner/crash-course", status_code=201)
def create(body: CourseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        cc = crashcourse.create(db, user.id, body.days, body.track, body.level, body.target, body.hours)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return crashcourse.view(db, cc)


@router.get("/planner/crash-course")
def get(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cc = _active(db, user)
    return crashcourse.view(db, cc) if cc else {"id": None, "message": "No crash course yet. Pick 30 or 60 days to start."}


@router.post("/planner/crash-course/tasks/{task_id}/toggle")
def toggle(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cc = _active(db, user)
    if cc is None or not any(t["id"] == task_id for p in cc.plan for t in p["tasks"]):
        raise HTTPException(404, "Task not found")
    done = set(cc.done or [])
    done.symmetric_difference_update({task_id})
    cc.done = sorted(done)  # reassign: JSON columns are not mutation-tracked
    db.commit()
    return crashcourse.view(db, cc)


@router.delete("/planner/crash-course", status_code=204)
def stop(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cc = _active(db, user)
    if cc:
        cc.active = False; db.commit()
