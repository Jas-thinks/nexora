from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.studio import _SLOTS
from app.arena import problems as P
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.execution import runner
from app.models.ai import MatchPlayer
from app.models.user import User
from app.services import arena

router = APIRouter(tags=["arena"])


@router.get("/arena/problems")
def problems(user: User = Depends(current_user)):
    return [{"key": k, "title": v["title"], "level": v["level"], "hidden_tests": len(v["tests"])} for k, v in P.PROBLEMS.items()]


@router.get("/arena/problems/{key}")
def problem(key: str, user: User = Depends(current_user)):
    if key not in P.PROBLEMS:
        raise HTTPException(404, "Unknown problem")
    return P.public(key)  # samples only; hidden tests are never exposed


class CreateIn(BaseModel):
    problem_key: str
    minutes: int = Field(20, ge=5, le=90)
    max_players: int = Field(2, ge=2, le=8)


@router.post("/arena/matches", status_code=201)
def create(body: CreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        m = arena.create(db, user.id, body.problem_key, body.minutes, body.max_players)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return arena.state(db, user.id, m.id)


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=8)


@router.post("/arena/matches/join")
def join(body: JoinIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        m = arena.join(db, user.id, body.code)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except PermissionError as e:
        raise HTTPException(409, str(e)) from None
    return arena.state(db, user.id, m.id)


@router.get("/arena/matches")
def mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = [i for (i,) in db.execute(select(MatchPlayer.match_id).where(MatchPlayer.user_id == user.id).order_by(MatchPlayer.id.desc()).limit(15))]
    return [arena.state(db, user.id, i) for i in ids]


@router.get("/arena/matches/{mid}")
def get(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return arena.state(db, user.id, mid)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None


@router.post("/arena/matches/{mid}/start")
def start(mid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        arena.start(db, user.id, mid)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except PermissionError as e:
        raise HTTPException(409, str(e)) from None
    return arena.state(db, user.id, mid)


class SubmitIn(BaseModel):
    language: str
    code: str = Field(max_length=runner.MAX_CODE)


@router.post("/arena/matches/{mid}/submit")
def submit(mid: int, body: SubmitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.language not in runner.LANGS:
        raise HTTPException(422, f"language must be one of {list(runner.LANGS)}")
    limiter.check(f"arena:{user.id}", 6, 60.0)
    if not _SLOTS.acquire(blocking=False):
        raise HTTPException(429, "The judge is busy. Try again in a few seconds.", headers={"Retry-After": "3"})
    try:
        return arena.submit(db, user.id, mid, body.language, body.code)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    except PermissionError as e:
        raise HTTPException(409, str(e)) from None
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None
    finally:
        _SLOTS.release()
