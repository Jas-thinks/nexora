from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.mentor import get_router
from app.core.db import get_db
from app.llm.router import Router
from app.models.ai import InterviewSession
from app.models.user import User
from app.services import interview, mentor

router = APIRouter(tags=["interview"])


class StartIn(BaseModel):
    minutes: int = 45


@router.post("/interview", status_code=201)
def start(body: StartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        s = interview.start(db, user.id, body.minutes)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    return interview.state(db, user.id, s.id)


@router.get("/interview")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": s.id, "status": s.status, "minutes": s.minutes, "started_at": s.started_at, "scores": (s.rubric or {}).get("scored", {}) and (s.rubric["scored"] or {}).get("scores")}
            for s in db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id).order_by(InterviewSession.id.desc()).limit(20))]


@router.get("/interview/{sid}")
def get(sid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return interview.state(db, user.id, sid)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None


class SayIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    code: str | None = Field(None, max_length=20000)


@router.post("/interview/{sid}/say")
def say(sid: int, body: SayIn, user: User = Depends(current_user), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    try:
        st = interview.state(db, user.id, sid)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    if st["status"] != "running":
        raise HTTPException(409, "This interview has finished")
    try:
        out = mentor.chat(db, r, user.id, body.message, "interview", interview._thread(sid), 1, st["problem"]["id"], body.code)
    except PermissionError as e:
        raise HTTPException(429, str(e)) from None
    return {"answer": out["answer"], "offline": out["offline"], "seconds_left": interview.state(db, user.id, sid)["seconds_left"]}


class FinishIn(BaseModel):
    self_eval: dict | None = None


@router.post("/interview/{sid}/finish")
def finish(sid: int, body: FinishIn, user: User = Depends(current_user), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    try:
        return interview.finish(db, r, user.id, sid, body.self_eval)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
