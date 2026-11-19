from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models.user import User
from app.services import gamification

router = APIRouter(tags=["gamification"])


@router.get("/gamification/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return gamification.profile(db, user.id)


@router.get("/gamification/leaderboard")
def board(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return gamification.leaderboard(db, user.id)
