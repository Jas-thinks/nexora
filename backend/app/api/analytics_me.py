from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models.user import User
from app.services import student_analytics

router = APIRouter(tags=["analytics"])


@router.get("/analytics/me")
def my_analytics(range: str = Query("90d"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return student_analytics.compute(db, user.id, range)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
