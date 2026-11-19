from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.models.catalog import Problem
from app.models.daily import ReviewItem, ReviewLog
from app.models.integrations import Submission
from app.models.user import User
from app.services import mistakes as M
from tests.conftest import auth, register

NOW = datetime(2026, 6, 15, 12, tzinfo=UTC)


def mk(db, ext, tags=("dp",)):
    p = Problem(platform="codeforces", external_id=ext, name=f"P{ext}", rating=1500, tags=list(tags), url="u", canonical_url="u"); db.add(p); db.flush(); return p


def sub(db, uid, p, v, days, n=0):
    db.add(Submission(user_id=uid, platform="codeforces", external_id=f"{uid}-{p.id}-{days}-{n}-{v}", problem_ref=p.external_id, problem_id=p.id, verdict=v, submitted_at=NOW - timedelta(days=days, minutes=n)))


@pytest.fixture()
def uid(client):
    register(client)
    with dbmod.SessionLocal() as db:
        return db.scalar(select(User.id))


def test_notebook_groups_failures_diagnoses_and_orders_open_first(client, uid):
    with dbmod.SessionLocal() as db:
        a, b, c = mk(db, "1"), mk(db, "2"), mk(db, "3")
        for i in range(3): sub(db, uid, a, "TLE", 5, i)                  # open, TLE-dominated
        for i in range(2): sub(db, uid, b, "WA", 6, i + 10)               # recovered after 2 WAs
        sub(db, uid, b, "AC", 5)
        sub(db, uid, c, "WA", 4)                                          # single failure: not listed
        db.commit()
        nb = M.notebook(db, uid)
    assert [x["problem"]["name"] for x in nb["items"]] == ["P1", "P2"] and nb["items"][0]["status"] == "open" and nb["items"][1]["status"] == "recovered"
    assert nb["items"][0]["diagnosis_kind"] == "efficiency" and "complexity" in nb["items"][0]["diagnosis"] and nb["items"][1]["failed_attempts"] == 2
    assert nb["recurring_patterns"][0]["failed_attempts"] == 5 and nb["verdict_mix"] == {"TLE": 3, "WA": 2}


def test_failures_after_the_first_ac_are_not_counted_as_mistakes(client, uid):
    with dbmod.SessionLocal() as db:
        a = mk(db, "1")
        sub(db, uid, a, "AC", 10); sub(db, uid, a, "WA", 5); sub(db, uid, a, "WA", 4); sub(db, uid, a, "WA", 3)
        db.commit()
        assert M.notebook(db, uid)["items"] == []


def test_notes_are_private_validated_and_surface_in_the_notebook(client, uid):
    with dbmod.SessionLocal() as db:
        a = mk(db, "1")
        for i in range(2): sub(db, uid, a, "WA", 3, i)
        db.commit(); pid = a.id
        with pytest.raises(ValueError):
            M.save_note(db, uid, pid, "x", "bad-cause")
        M.save_note(db, uid, pid, "Forgot n=1", "edge-case")
        it = M.notebook(db, uid)["items"][0]
        assert it["note"] == "Forgot n=1" and it["cause"] == "edge-case"


def test_recovered_struggles_are_scheduled_for_review_once(client, uid):
    with dbmod.SessionLocal() as db:
        a, b = mk(db, "1"), mk(db, "2")
        for i in range(2): sub(db, uid, a, "WA", 6, i + 5)
        sub(db, uid, a, "AC", 5); sub(db, uid, b, "AC", 5)
        db.commit()
        assert M.enroll_recovered(db, uid, NOW) == 1 and M.enroll_recovered(db, uid, NOW) == 0
        rv = db.scalar(select(ReviewItem)); assert rv.problem_id == a.id and rv.box == 0 and rv.last_result == "struggled"


def test_review_moves_boxes_logs_and_validates(client, uid):
    with dbmod.SessionLocal() as db:
        a = mk(db, "1")
        db.add(ReviewItem(user_id=uid, problem_id=a.id, due_at=NOW - timedelta(days=2), box=1)); db.commit()
        assert M.review(db, uid, a.id, "good", NOW).box == 2
        rv = M.review(db, uid, a.id, "again", NOW)
        assert rv.box == 0 and rv.due_at.replace(tzinfo=UTC) == NOW + timedelta(days=1)
        with pytest.raises(ValueError): M.review(db, uid, a.id, "meh")
        with pytest.raises(LookupError): M.review(db, uid, 9999, "good")
        logs = db.scalars(select(ReviewLog).order_by(ReviewLog.id)).all()
        assert [(l.result, l.was_due) for l in logs] == [("good", True), ("again", False)]


def test_overview_buckets_due_upcoming_and_consistency(client, uid):
    with dbmod.SessionLocal() as db:
        ps = [mk(db, str(i)) for i in range(4)]
        db.add_all([ReviewItem(user_id=uid, problem_id=ps[0].id, due_at=NOW - timedelta(days=3), box=0), ReviewItem(user_id=uid, problem_id=ps[1].id, due_at=NOW + timedelta(days=2), box=2),
                    ReviewItem(user_id=uid, problem_id=ps[2].id, due_at=NOW + timedelta(days=30), box=3)])
        db.add_all([ReviewLog(user_id=uid, problem_id=ps[3].id, result="good", was_due=True, at=NOW - timedelta(days=1)), ReviewLog(user_id=uid, problem_id=ps[3].id, result="again", was_due=False, at=NOW - timedelta(days=2))])
        db.commit()
        o = M.overview(db, uid, NOW)
    assert len(o["due"]) == 1 and len(o["upcoming_7d"]) == 1 and o["total_scheduled"] == 3 and o["boxes"] == {0: 1, 2: 1, 3: 1}
    assert o["consistency"]["good_rate"] == 0.5 and o["consistency"]["on_time_rate"] == 0.5 and o["consistency"]["avg_days_overdue_now"] == 3.0


def test_empty_overview_has_none_not_zero_rates(client, uid):
    with dbmod.SessionLocal() as db:
        c = M.overview(db, uid, NOW)["consistency"]
    assert c["good_rate"] is None and c["on_time_rate"] is None and c["reviews_90d"] == 0


def test_api_auth_validation_and_isolation(client, uid):
    h = auth(client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    assert client.get("/mistakes").status_code == 401
    with dbmod.SessionLocal() as db:
        a = mk(db, "1"); pid = a.id; db.commit()
    assert client.put(f"/mistakes/{pid}/note", headers=h, json={"note": "n", "cause": "careless"}).json()["saved"]
    assert client.put(f"/mistakes/{pid}/note", headers=h, json={"note": "n", "cause": "nope"}).status_code == 422
    assert client.put("/mistakes/9999/note", headers=h, json={"note": "n"}).status_code == 404
    assert client.post(f"/revision/{pid}/review", headers=h, json={"result": "good"}).status_code == 404
    assert client.post(f"/revision/{pid}/review", headers=h, json={"result": "maybe"}).status_code == 422
    other = auth(register(client, "b@example.com"))
    assert client.get("/mistakes", headers=other).json()["items"] == [] and client.get("/revision/overview", headers=other).json()["total_scheduled"] == 0
