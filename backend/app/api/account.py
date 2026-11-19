import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core import totp
from app.core.config import get_settings
from app.core.db import get_db
from app.core.ratelimit import auth_rate_limit, limiter
from app.core.security import hash_password, verify_password
from app.models.user import AuditLog, AuthToken, RefreshToken, User, UserMFA
from app.services.notifications import send_email

router = APIRouter(prefix="/auth", tags=["account"])
log = logging.getLogger("nexora.account")


def _issue(db: Session, user: User, kind: str, ttl: timedelta) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(user_id=user.id, kind=kind, token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=datetime.now(UTC) + ttl)); db.commit()
    return raw


def _consume(db: Session, raw: str, kind: str) -> User:
    t = db.scalar(select(AuthToken).where(AuthToken.token_hash == hashlib.sha256(raw.encode()).hexdigest(), AuthToken.kind == kind))
    exp = t.expires_at if t and t.expires_at.tzinfo else (t.expires_at.replace(tzinfo=UTC) if t else None)
    if t is None or t.used or exp < datetime.now(UTC):
        raise HTTPException(400, "This link is invalid or has expired")
    t.used = True; db.commit()
    return db.get(User, t.user_id)


def _mail(email: str, subject: str, link: str) -> None:
    if not send_email(email, subject, f"{link}\n\nIf you did not request this, ignore this email."):
        # no SMTP configured: never pretend. In dev the link is logged so the flow is testable; in prod nothing is leaked.
        if get_settings().env != "prod":
            log.warning("EMAIL NOT SENT (SMTP not configured) to=%s subject=%s link=%s", email, subject, link)


class ForgotIn(BaseModel):
    email: EmailStr


@router.post("/forgot", status_code=202, dependencies=[Depends(auth_rate_limit)])
def forgot(body: ForgotIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and u.is_active:
        _mail(u.email, "Reset your Nexora password", f"/reset?token={_issue(db, u, 'reset', timedelta(hours=1))}")
    return {"ok": True, "message": "If that email has an account, a reset link is on its way."}  # identical response: no account enumeration


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=128)


@router.post("/reset", dependencies=[Depends(auth_rate_limit)])
def reset(body: ResetIn, db: Session = Depends(get_db)):
    u = _consume(db, body.token, "reset")
    u.password_hash = hash_password(body.password)
    db.execute(update(RefreshToken).where(RefreshToken.user_id == u.id).values(revoked=True))  # every session ends
    db.add(AuditLog(user_id=u.id, action="auth.password_reset", detail={})); db.commit()
    return {"ok": True}


@router.post("/verify/request", status_code=202)
def request_verify(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.email_verified:
        return {"ok": True, "already_verified": True}
    limiter.check(f"verify:{user.id}", 3, 3600.0)
    _mail(user.email, "Verify your Nexora email", f"/verify?token={_issue(db, user, 'verify', timedelta(days=3))}")
    return {"ok": True}


class TokIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/verify")
def verify_email(body: TokIn, db: Session = Depends(get_db)):
    u = _consume(db, body.token, "verify")
    u.email_verified = True; db.commit()
    return {"ok": True}


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(UserMFA, user.id)
    if m and m.enabled:
        raise HTTPException(409, "MFA is already enabled")
    sec = totp.new_secret()
    if m is None:
        m = UserMFA(user_id=user.id, secret=sec); db.add(m)
    m.secret, m.enabled, m.last_counter = sec, False, 0
    db.commit()
    return {"secret": sec, "otpauth_uri": totp.uri(sec, user.email), "note": "Add it to an authenticator app, then confirm with a code to enable."}


@router.post("/mfa/enable")
def mfa_enable(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"mfa:{user.id}", 8, 300.0)
    m = db.get(UserMFA, user.id)
    c = totp.verify(m.secret, body.code, m.last_counter) if m else None
    if c is None:
        raise HTTPException(400, "Invalid code")
    m.enabled, m.last_counter = True, c
    db.add(AuditLog(user_id=user.id, action="auth.mfa_enabled", detail={})); db.commit()
    return {"enabled": True}


class DisableIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(max_length=128)


@router.post("/mfa/disable")
def mfa_disable(body: DisableIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"mfa:{user.id}", 8, 300.0)
    m = db.get(UserMFA, user.id)
    if not m or not m.enabled or not verify_password(body.password, user.password_hash) or totp.verify(m.secret, body.code, m.last_counter) is None:
        raise HTTPException(400, "Invalid code or password")
    db.delete(m); db.add(AuditLog(user_id=user.id, action="auth.mfa_disabled", detail={})); db.commit()
    return {"enabled": False}
