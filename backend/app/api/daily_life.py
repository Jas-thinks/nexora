from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models.ai import Goal, Notification
from app.models.user import User
from app.services import contest_prep, notifications, planner

router = APIRouter(tags=["daily-life"])


@router.get("/notifications")
def list_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    notifications.generate(db, user.id)  # cheap and idempotent: keeps the bell fresh without waiting for the scheduler
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(30)).all()
    return {"unread": sum(not n.read for n in rows), "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "href": n.href, "read": n.read, "created_at": n.created_at} for n in rows]}


@router.post("/notifications/read")
def mark_read(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(read=True)); db.commit()
    return {"ok": True}


@router.get("/contests/{cid}/prep")
def prep(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return contest_prep.prep(db, user.id, cid)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None


@router.get("/contests/{cid}/review")
def review(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return contest_prep.review(db, user.id, cid)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None


class GoalIn(BaseModel):
    target: int = Field(ge=800, le=4000)
    deadline: datetime
    platform: str = Field("codeforces", pattern="^(codeforces)$")


@router.get("/planner")
def get_plan(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return planner.plan(db, user.id)


@router.put("/planner/goal")
def put_goal(body: GoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        planner.set_goal(db, user.id, body.target, body.deadline if body.deadline.tzinfo else body.deadline.replace(tzinfo=UTC), body.platform)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return planner.plan(db, user.id)


@router.delete("/planner/goal", status_code=204)
def del_goal(user: User = Depends(current_user), db: Session = Depends(get_db)):
    g = db.scalar(select(Goal).where(Goal.user_id == user.id))
    if g: db.delete(g); db.commit()
