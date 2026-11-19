from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.ratelimit import auth_rate_limit
from app.core.security import (
    create_access_token, hash_password, hash_refresh, new_refresh_token, verify_password,
)
from app.models.user import AuditLog, RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the email is unknown so login timing does not reveal account existence.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    otp: str | None = Field(None, max_length=6)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    email_verified: bool = False
    mfa_enabled: bool = False


def _audit(db: Session, user_id: int | None, action: str, **detail) -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))


def _issue(db: Session, user: User) -> TokenOut:
    raw, hashed = new_refresh_token()
    exp = datetime.now(UTC) + timedelta(days=get_settings().refresh_ttl_days)
    db.add(RefreshToken(user_id=user.id, token_hash=hashed, expires_at=exp))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role), refresh_token=raw)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@router.post("/register", response_model=TokenOut, status_code=201, dependencies=[Depends(auth_rate_limit)])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=email, display_name=body.display_name.strip(),
                password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    _audit(db, user.id, "user.register")
    return _issue(db, user)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        _audit(db, user.id if user else None, "user.login_failed")
        db.commit()
        raise HTTPException(401, "Invalid credentials")
    from app.core import totp
    from app.models.user import UserMFA
    m = db.get(UserMFA, user.id)
    if m and m.enabled:  # password was right; the second factor is checked before any token is issued
        c = totp.verify(m.secret, body.otp or "", m.last_counter) if body.otp else None
        if c is None:
            _audit(db, user.id, "user.login_mfa_failed"); db.commit()
            raise HTTPException(401, "mfa_required" if not body.otp else "Invalid code")
        m.last_counter = c
    _audit(db, user.id, "user.login")
    return _issue(db, user)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh(body.refresh_token)))
    if tok is None:
        raise HTTPException(401, "Invalid refresh token")
    if tok.revoked:
        # Reuse of a rotated token => assume theft, kill the whole family.
        for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == tok.user_id)):
            t.revoked = True
        _audit(db, tok.user_id, "auth.refresh_reuse_detected")
        db.commit()
        raise HTTPException(401, "Invalid refresh token")
    if _aware(tok.expires_at) < datetime.now(UTC):
        raise HTTPException(401, "Refresh token expired")
    user = db.get(User, tok.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User disabled")
    tok.revoked = True
    return _issue(db, user)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    tok = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh(body.refresh_token)))
    if tok:
        tok.revoked = True
        db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.models.user import UserMFA
    m = db.get(UserMFA, user.id)
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, role=user.role, email_verified=user.email_verified, mfa_enabled=bool(m and m.enabled))


@router.get("/me/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    logs = db.scalars(select(AuditLog).where(AuditLog.user_id == user.id)).all()
    return {
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name,
                 "role": user.role, "created_at": user.created_at.isoformat()},
        "audit_log": [{"action": l.action, "at": l.created_at.isoformat()} for l in logs],
    }


@router.delete("/me", status_code=204)
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    # Keep an anonymised trail of the deletion itself; drop the user's own history.
    db.execute(delete(AuditLog).where(AuditLog.user_id == user.id))
    _audit(db, None, "user.deleted")
    db.delete(user)
    db.commit()
