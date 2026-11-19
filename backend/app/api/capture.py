from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import hash_refresh
from app.models.user import ApiToken, User
from app.services import capture

router = APIRouter(tags=["capture"])
PREFIX = "nxc_"


class TokenIn(BaseModel):
    label: str = Field("browser extension", min_length=1, max_length=60)


@router.post("/capture/tokens", status_code=201)
def create_token(body: TokenIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import secrets
    if len(db.scalars(select(ApiToken.id).where(ApiToken.user_id == user.id, ApiToken.revoked.is_(False))).all()) >= 5:
        raise HTTPException(409, "You already have 5 active capture tokens. Revoke one first.")
    raw = PREFIX + secrets.token_urlsafe(32)
    t = ApiToken(user_id=user.id, label=body.label, prefix=raw[:10], token_hash=hash_refresh(raw)); db.add(t); db.commit()
    return {"id": t.id, "token": raw, "label": t.label, "note": "Shown once. It can only upload submissions captured by your browser; it cannot read your data."}


@router.get("/capture/tokens")
def list_tokens(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": t.id, "label": t.label, "prefix": t.prefix, "created_at": t.created_at, "last_used_at": t.last_used_at, "revoked": t.revoked}
            for t in db.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id.desc()))]


@router.delete("/capture/tokens/{tid}", status_code=204)
def revoke(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(ApiToken, tid)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "Token not found")
    t.revoked = True; db.commit()


class Item(BaseModel):
    id: str | None = Field(None, max_length=80)
    problem_url: str = Field(max_length=300)
    verdict: str = Field(max_length=60)
    submitted_at: str = Field(max_length=40)
    language: str | None = Field(None, max_length=80)
    time_ms: int | None = None


class BatchIn(BaseModel):
    platform: str = Field(max_length=40)
    submissions: list[Item] = Field(max_length=capture.MAX_BATCH)


@router.post("/capture/submissions")
def upload(body: BatchIn, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    """Token-authenticated (NOT a user JWT): the extension's key can do nothing else."""
    raw = (authorization or "").removeprefix("Bearer ").strip()
    t = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_refresh(raw))) if raw.startswith(PREFIX) else None
    if t is None or t.revoked:
        raise HTTPException(401, "Invalid or revoked capture token")
    limiter.check(f"capture:{t.id}", 30, 60.0)
    try:
        res = capture.ingest_batch(db, t.user_id, body.platform, [i.model_dump() for i in body.submissions])
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    t.last_used_at = datetime.now(UTC); db.commit()
    return res
