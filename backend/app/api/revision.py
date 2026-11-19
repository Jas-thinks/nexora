from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models.catalog import Problem
from app.models.user import User
from app.services import mistakes

router = APIRouter(tags=["revision"])


@router.get("/mistakes")
def get_mistakes(limit: int = Query(40, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return mistakes.notebook(db, user.id, limit)


class NoteIn(BaseModel):
    note: str = Field("", max_length=2000)
    cause: str | None = None


@router.put("/mistakes/{pid}/note")
def put_note(pid: int, body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Problem, pid) is None:
        raise HTTPException(404, "Problem not found")
    try:
        n = mistakes.save_note(db, user.id, pid, body.note, body.cause)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"saved": True, "cause": n.cause}


@router.get("/revision/overview")
def revision_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return mistakes.overview(db, user.id)


class ReviewIn(BaseModel):
    result: str = Field(pattern="^(good|again)$")


@router.post("/revision/{pid}/review")
def do_review(pid: int, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        rv = mistakes.review(db, user.id, pid, body.result)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    return {"box": rv.box, "next_due": rv.due_at}
