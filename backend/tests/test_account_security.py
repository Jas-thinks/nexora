import hashlib
import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.core import totp
from app.models.user import AuthToken
from tests.conftest import auth, register

PW = "correct-horse-battery"


def test_totp_matches_rfc6238_vectors():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # ASCII "12345678901234567890" (RFC 6238 appendix B, SHA-1)
    for t, expected in ((59, "287082"), (1111111109, "081804"), (1111111111, "050471"), (1234567890, "005924"), (2000000000, "279037")):
        assert totp.code_at(secret, t // 30) == expected


def test_totp_verify_window_replay_and_format():
    s = totp.new_secret(); now = 1_700_000_000.0; c = int(now // 30)
    assert totp.verify(s, totp.code_at(s, c), 0, now) == c
    assert totp.verify(s, totp.code_at(s, c - 1), 0, now) == c - 1 and totp.verify(s, totp.code_at(s, c + 5), 0, now) is None  # drift tolerated, far future not
    assert totp.verify(s, totp.code_at(s, c), c, now) is None  # same code cannot be replayed
    assert totp.verify(s, "12345", 0, now) is None and totp.verify(s, "abcdef", 0, now) is None


@pytest.fixture()
def tokens(client, caplog):
    caplog.set_level(logging.WARNING, logger="nexora.account")
    def grab():
        for r in reversed(caplog.records):
            if "link=" in r.getMessage():
                return r.getMessage().split("token=")[1].strip()
    return grab


def test_forgot_never_reveals_whether_an_account_exists(client):
    register(client)
    a = client.post("/auth/forgot", json={"email": "a@example.com"}); b = client.post("/auth/forgot", json={"email": "ghost@example.com"})
    assert a.status_code == b.status_code == 202 and a.json() == b.json()


def test_reset_flow_is_single_use_expires_and_revokes_sessions(client, tokens):
    t = register(client)
    client.post("/auth/forgot", json={"email": "a@example.com"}); tok = tokens()
    assert tok and client.post("/auth/reset", json={"token": "x" * 20, "password": "brand-new-password"}).status_code == 400
    assert client.post("/auth/reset", json={"token": tok, "password": "short"}).status_code == 422
    assert client.post("/auth/reset", json={"token": tok, "password": "brand-new-password"}).status_code == 200
    assert client.post("/auth/reset", json={"token": tok, "password": "another-new-password"}).status_code == 400  # single use
    assert client.post("/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 401
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "brand-new-password"}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401  # old session revoked
    with dbmod.SessionLocal() as db:  # token stored only as a hash
        assert db.scalar(select(AuthToken.token_hash)) == hashlib.sha256(tok.encode()).hexdigest() and tok not in str(db.scalars(select(AuthToken.token_hash)).all())


def test_expired_reset_token_is_rejected(client, tokens):
    register(client); client.post("/auth/forgot", json={"email": "a@example.com"}); tok = tokens()
    with dbmod.SessionLocal() as db:
        t = db.scalar(select(AuthToken)); t.expires_at = datetime.now(UTC) - timedelta(minutes=1); db.commit()
    assert client.post("/auth/reset", json={"token": tok, "password": "brand-new-password"}).status_code == 400


def test_email_verification_flow_and_cross_kind_tokens_do_not_work(client, tokens):
    t = register(client); h = auth(t)
    assert client.get("/auth/me", headers=h).json()["email_verified"] is False
    client.post("/auth/verify/request", headers=h); tok = tokens()
    assert client.post("/auth/reset", json={"token": tok, "password": "brand-new-password"}).status_code == 400  # a verify token cannot reset a password
    client.post("/auth/verify/request", headers=h); tok = tokens()
    assert client.post("/auth/verify", json={"token": tok}).status_code == 200 and client.get("/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/auth/verify/request", headers=h).json()["already_verified"] is True


def test_mfa_setup_enable_login_replay_and_disable(client, monkeypatch):
    t = register(client); h = auth(t)
    s = client.post("/auth/mfa/setup", headers=h).json(); assert s["otpauth_uri"].startswith("otpauth://totp/Nexora:") and s["secret"]
    assert client.post("/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code == 400
    c = int(datetime.now(UTC).timestamp() // 30)
    assert client.post("/auth/mfa/enable", headers=h, json={"code": totp.code_at(s["secret"], c)}).json()["enabled"] is True
    assert client.get("/auth/me", headers=h).json()["mfa_enabled"] is True and client.post("/auth/mfa/setup", headers=h).status_code == 409
    r = client.post("/auth/login", json={"email": "a@example.com", "password": PW}); assert r.status_code == 401 and r.json()["detail"] == "mfa_required"
    assert client.post("/auth/login", json={"email": "a@example.com", "password": PW, "otp": "000000"}).status_code == 401
    assert client.post("/auth/login", json={"email": "a@example.com", "password": PW, "otp": totp.code_at(s["secret"], c)}).status_code == 401  # already used to enable: replay blocked
    ok = client.post("/auth/login", json={"email": "a@example.com", "password": PW, "otp": totp.code_at(s["secret"], c + 1)})
    assert ok.status_code == 200 and "access_token" in ok.json()
    monkeypatch.setattr(totp.time, "time", lambda: (c + 2) * 30 + 1)  # 30 s later: the next step's code is now inside the drift window
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password-1", "otp": totp.code_at(s["secret"], c + 2)}).status_code == 401  # wrong password: no hint about MFA state
    assert client.post("/auth/mfa/disable", headers=h, json={"code": totp.code_at(s["secret"], c + 2), "password": "wrong-password-1"}).status_code == 400
    assert client.post("/auth/mfa/disable", headers=h, json={"code": totp.code_at(s["secret"], c + 2), "password": PW}).json()["enabled"] is False
    assert client.post("/auth/login", json={"email": "a@example.com", "password": PW}).status_code == 200


def test_mfa_endpoints_require_auth_and_are_rate_limited(client):
    assert client.post("/auth/mfa/setup").status_code == 401
    h = auth(register(client)); client.post("/auth/mfa/setup", headers=h)
    codes = [client.post("/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code for _ in range(10)]
    assert codes[:8] == [400] * 8 and codes[8:] == [429, 429]
