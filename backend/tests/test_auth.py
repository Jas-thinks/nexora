import jwt
import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.core.config import get_settings
from app.models.user import AuditLog, User
from tests.conftest import auth, register


def test_register_login_me(client):
    register(client)
    r = client.post("/auth/login", json={"email": "A@Example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200
    me = client.get("/auth/me", headers=auth(r.json()))
    assert me.json()["email"] == "a@example.com"


def test_password_stored_hashed(client):
    register(client)
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User))
        assert u.password_hash.startswith("scrypt$") and "correct-horse" not in u.password_hash


def test_duplicate_email_rejected(client):
    register(client)
    r = client.post("/auth/register", json={"email": "a@example.com", "display_name": "x", "password": "another-long-pass"})
    assert r.status_code == 409


def test_weak_password_and_bad_email_rejected(client):
    assert client.post("/auth/register", json={"email": "b@example.com", "display_name": "x", "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={"email": "nope", "display_name": "x", "password": "long-enough-pass"}).status_code == 422


def test_wrong_password_and_unknown_user_same_response(client):
    register(client)
    r1 = client.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password-1"})
    r2 = client.post("/auth/login", json={"email": "ghost@example.com", "password": "wrong-password-1"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_protected_routes_require_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_expired_and_refresh_type_tokens_rejected(client):
    register(client)
    s = get_settings()
    expired = jwt.encode({"sub": "1", "typ": "access", "exp": 1}, s.jwt_secret, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    wrong_type = jwt.encode({"sub": "1", "typ": "refresh", "exp": 9999999999}, s.jwt_secret, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {wrong_type}"}).status_code == 401
    forged = jwt.encode({"sub": "1", "typ": "access", "exp": 9999999999}, "other-secret-other-secret-other!", algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    t = register(client)
    r = client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    # Replaying the old token fails AND revokes the whole family.
    assert client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401


def test_logout_revokes_refresh(client):
    t = register(client)
    assert client.post("/auth/logout", json={"refresh_token": t["refresh_token"]}).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


def test_role_enforcement(client):
    from fastapi import Depends
    from app.api.deps import require_role
    t = register(client)
    app = client.app
    app.add_api_route("/admin-only", lambda u=Depends(require_role("admin")): {"ok": True})
    assert client.get("/admin-only", headers=auth(t)).status_code == 403
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User)); u.role = "admin"; db.commit()
    t2 = client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json()
    assert client.get("/admin-only", headers=auth(t2)).status_code == 200


def test_export_and_delete_account(client):
    t = register(client)
    exp = client.get("/auth/me/export", headers=auth(t)).json()
    assert exp["user"]["email"] == "a@example.com" and "password_hash" not in str(exp)
    assert client.delete("/auth/me", headers=auth(t)).status_code == 204
    assert client.get("/auth/me", headers=auth(t)).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401
    with dbmod.SessionLocal() as db:
        assert db.scalar(select(User)) is None
        assert all(l.user_id is None for l in db.scalars(select(AuditLog)))


def test_auth_rate_limit(client, monkeypatch):
    monkeypatch.setenv("CODEMIND_AUTH_RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    try:
        codes = [client.post("/auth/login", json={"email": "z@example.com", "password": "whatever-pass"}).status_code
                 for _ in range(5)]
        assert codes[:3] == [401] * 3 and codes[3:] == [429] * 2
    finally:
        get_settings.cache_clear()


def test_prod_refuses_default_secret(monkeypatch):
    monkeypatch.setenv("CODEMIND_ENV", "prod")
    get_settings.cache_clear()
    try:
        from app.main import create_app
        with pytest.raises(RuntimeError):
            create_app()
    finally:
        get_settings.cache_clear()
