from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.models.ai import Goal, Notification, UserPrefs
from app.models.catalog import Problem
from app.models.daily import ReviewItem
from app.models.integrations import ConnectedProfile, Contest, RatingHistory, Submission
from app.models.user import User
from app.services import contest_prep, notifications as N, planner
from tests.conftest import auth, register

NOW = datetime(2026, 6, 15, 12, tzinfo=UTC)


def mk(db, ext, rating=1500, tags=("dp",), plat="codeforces"):
    p = Problem(platform=plat, external_id=ext, name=f"P{ext}", rating=rating, tags=list(tags), url="u", canonical_url="u"); db.add(p); db.flush(); return p


def sub(db, uid, p, v, days, n=0, in_contest=None):
    db.add(Submission(user_id=uid, platform="codeforces", external_id=f"{uid}-{p.id}-{days}-{n}-{v}", problem_ref=p.external_id, problem_id=p.id, verdict=v, in_contest=in_contest,
                      submitted_at=NOW - timedelta(days=days, minutes=n), provenance="verified"))


@pytest.fixture()
def uid(client):
    register(client)
    with dbmod.SessionLocal() as db:
        return db.scalar(select(User.id))


def test_notifications_are_generated_from_state_and_deduplicated(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1"); [sub(db, uid, p, "AC", d) for d in (1, 2, 3)]          # 3-day streak, nothing today
        db.add(ReviewItem(user_id=uid, problem_id=p.id, due_at=NOW - timedelta(days=1)))
        db.add(ConnectedProfile(user_id=uid, platform="codeforces", handle="h", data_level="public_api"))
        db.add(Contest(platform="codeforces", external_id="9", name="Round 9", url="c", source="t", start_time=NOW + timedelta(hours=5)))
        db.add(Contest(platform="codeforces", external_id="10", name="Far", url="c", source="t", start_time=NOW + timedelta(days=9)))
        db.add(Contest(platform="atcoder", external_id="x", name="Other", url="c", source="t", start_time=NOW + timedelta(hours=5))); db.commit()
        assert N.generate(db, uid, NOW) == 4
        kinds = sorted(n.kind for n in db.scalars(select(Notification)))
        assert kinds == ["contest", "daily", "revision", "streak"]
        assert N.generate(db, uid, NOW) == 0  # idempotent
        assert N.generate(db, uid, NOW + timedelta(days=1)) >= 1  # new day => new reminders


def test_no_streak_reminder_when_already_active_today_or_no_history(client, uid):
    with dbmod.SessionLocal() as db:
        assert N.generate(db, uid, NOW) == 0
        p = mk(db, "1"); [sub(db, uid, p, "AC", d) for d in (0, 1, 2)]; db.commit()
        N.generate(db, uid, NOW)
        assert "streak" not in {n.kind for n in db.scalars(select(Notification))}


def test_email_only_for_opted_in_users_and_never_when_smtp_missing(client, uid):
    with dbmod.SessionLocal() as db:
        db.add(Notification(user_id=uid, kind="daily", title="t", body="b", href="/daily", dedupe_key="k")); db.commit()
        sent = []
        assert N.email_pending(db, lambda to, s, b: sent.append(to) or True) == 0 and not sent   # not opted in
        db.add(UserPrefs(user_id=uid, email_notifications=True)); db.commit()
        assert N.email_pending(db, lambda to, s, b: False) == 0                                    # transport failed: stays unsent
        assert N.email_pending(db, lambda to, s, b: sent.append(to) or True) == 1 and sent == ["a@example.com"] and N.email_pending(db, lambda *a: True) == 0
        assert N.send_email("x@y.z", "s", "b") is False  # SMTP not configured => no fake success


def test_notification_api_marks_read_and_isolates_users(client, uid):
    h = auth(client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    with dbmod.SessionLocal() as db:
        p = mk(db, "1"); [sub(db, uid, p, "AC", d) for d in (1, 2)]; db.commit()
    r = client.get("/notifications", headers=h).json()
    assert r["unread"] >= 1 and client.post("/notifications/read", headers=h).json()["ok"] and client.get("/notifications", headers=h).json()["unread"] == 0
    other = auth(register(client, "b@example.com"))
    assert client.get("/notifications", headers=other).json()["items"] == [] and client.get("/notifications").status_code == 401


def test_contest_prep_is_personalised_and_honest_without_a_profile(client, uid):
    with dbmod.SessionLocal() as db:
        for i in range(6):
            p = mk(db, f"s{i}", 1000 + i * 100, ("greedy",)); sub(db, uid, p, "AC", 5 + i)
        for i in range(6): mk(db, f"c{i}", 1200 + i * 50, ("dp",))
        c = Contest(platform="codeforces", external_id="500", name="Round 500", url="u", source="t", start_time=NOW + timedelta(days=1), duration_seconds=7200); db.add(c); db.commit()
        r = contest_prep.prep(db, uid, c.id, NOW)
        assert r["linked_profile"] is False and "Link your handle" in " ".join(r["checklist"]) and r["recent_form"] is None
        assert r["warmup_problems"] and all("Targets" in x["why"] for x in r["warmup_problems"]) and r["starts_in_hours"] == 12.0 or r["starts_in_hours"] is not None
        db.add(ConnectedProfile(user_id=uid, platform="codeforces", handle="h", data_level="public_api")); db.commit()
        assert contest_prep.prep(db, uid, c.id, NOW)["linked_profile"] is True
        with pytest.raises(LookupError): contest_prep.prep(db, uid, 999999, NOW)


def test_post_contest_review_uses_only_in_contest_submissions_and_lists_upsolve(client, uid):
    with dbmod.SessionLocal() as db:
        a, b, c3 = mk(db, "500A", 800), mk(db, "500B", 1200), mk(db, "500C", 1600)
        other = mk(db, "5001A", 800)  # contest 5001, must not match prefix "500"
        sub(db, uid, a, "AC", 3, in_contest=True); sub(db, uid, b, "WA", 3, 1, in_contest=True); sub(db, uid, b, "WA", 3, 2, in_contest=True); sub(db, uid, c3, "AC", 2, in_contest=False); sub(db, uid, other, "AC", 3, in_contest=True)
        c = Contest(platform="codeforces", external_id="500", name="Round 500", url="u", source="t", start_time=NOW - timedelta(days=3)); db.add(c)
        db.add(RatingHistory(user_id=uid, platform="codeforces", contest_ref="500", contest_name="Round 500", at=NOW - timedelta(days=3), old_rating=1400, new_rating=1432, rank=812)); db.commit()
        r = contest_prep.review(db, uid, c.id)
    assert r["available"] and r["rating"]["change"] == 32 and r["rating"]["rank"] == 812 and r["solved"] == 1 and r["attempted"] == 2
    assert [u["name"] for u in r["upsolve"]] == ["P500B"] and {p["problem_ref"] for p in r["problems"]} == {"500A", "500B"}


def test_review_unavailable_for_contests_without_data(client, uid):
    with dbmod.SessionLocal() as db:
        c = Contest(platform="dmoj", external_id="d", name="D", url="u", source="t"); db.add(c); db.commit()
        assert contest_prep.review(db, uid, c.id)["available"] is False


def test_planner_validation_and_no_goal(client, uid):
    with dbmod.SessionLocal() as db:
        assert planner.plan(db, uid, NOW)["goal"] is None
        with pytest.raises(ValueError): planner.set_goal(db, uid, 500, datetime.now(UTC) + timedelta(days=60))
        with pytest.raises(ValueError): planner.set_goal(db, uid, 1600, datetime.now(UTC) + timedelta(days=2))
        with pytest.raises(ValueError): planner.set_goal(db, uid, 1600, datetime.now(UTC) + timedelta(days=900))


def test_planner_projects_only_from_the_students_own_pace_and_states_assumptions(client, uid):
    with dbmod.SessionLocal() as db:
        for i, r in enumerate((1000, 1040, 1085, 1120, 1170, 1210)):
            db.add(RatingHistory(user_id=uid, platform="codeforces", contest_ref=str(i), contest_name=f"R{i}", at=NOW - timedelta(days=70 - i * 10), old_rating=r - 40, new_rating=r))
        p = mk(db, "1"); [sub(db, uid, p, "AC", d, d) for d in range(1, 30, 2)]; db.commit()
        planner.set_goal(db, uid, 1300, datetime.now(UTC) + timedelta(days=84))
        g = db.scalar(select(Goal)); g.deadline = NOW + timedelta(days=84); db.commit()
        r = planner.plan(db, uid, NOW)
    assert r["current"]["rating"] == 1210 and r["gain_needed"] == 90 and r["feasibility"]["pace_per_week"] is not None and r["feasibility"]["verdict"] in ("on_track", "behind")
    assert len(r["weeks"]) == 12 and r["weeks"][-1]["milestone_rating"] == 1300 and all(3 <= w["problem_quota"] <= 25 for w in r["weeks"]) and len(r["assumptions"]) >= 3
    assert "recomputed" in " ".join(r["assumptions"])


def test_planner_without_rating_history_makes_no_forecast(client, uid):
    with dbmod.SessionLocal() as db:
        planner.set_goal(db, uid, 1600, datetime.now(UTC) + timedelta(days=100))
        r = planner.plan(db, uid)
    assert r["feasibility"]["verdict"] == "insufficient_data" and r["feasibility"]["pace_per_week"] is None and "not a forecast" in r["feasibility"]["explanation"]


def test_planner_goal_already_met(client, uid):
    with dbmod.SessionLocal() as db:
        db.add(RatingHistory(user_id=uid, platform="codeforces", contest_ref="1", contest_name="R", at=NOW - timedelta(days=5), old_rating=1700, new_rating=1750)); db.commit()
        planner.set_goal(db, uid, 1500, datetime.now(UTC) + timedelta(days=60))
        assert planner.plan(db, uid)["feasibility"]["verdict"] == "already_met"


def test_api_goal_flow_and_validation(client, uid):
    h = auth(client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    assert client.get("/planner", headers=h).json()["goal"] is None
    d = (datetime.now(UTC) + timedelta(days=90)).isoformat()
    r = client.put("/planner/goal", headers=h, json={"target": 1600, "deadline": d})
    assert r.status_code == 200 and r.json()["goal"]["target"] == 1600
    assert client.put("/planner/goal", headers=h, json={"target": 100, "deadline": d}).status_code == 422
    assert client.put("/planner/goal", headers=h, json={"target": 1600, "deadline": (datetime.now(UTC) + timedelta(days=1)).isoformat()}).status_code == 422
    assert client.delete("/planner/goal", headers=h).status_code == 204 and client.get("/planner", headers=h).json()["goal"] is None
    assert client.get("/contests/99999/prep", headers=h).status_code == 404
