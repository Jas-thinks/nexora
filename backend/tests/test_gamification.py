"""Gamification tests use SYNTHETIC events built in-test."""
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.models.catalog import Problem, ProblemStatus
from app.models.daily import DailyChallenge
from app.models.integrations import Submission
from app.models.user import User
from app.services import gamification as g
from tests.conftest import auth, register

TODAY = date(2026, 6, 15)
NOW = datetime(2026, 6, 15, 12, tzinfo=UTC)


def mk(db, ext, rating, tags=("math",)):
    p = Problem(platform="codeforces", external_id=ext, name=f"P{ext}", rating=rating, tags=list(tags), url="u", canonical_url="u")
    db.add(p); db.flush(); return p


def sub(db, uid, p, verdict, days_ago, n=0, prov="verified"):
    db.add(Submission(user_id=uid, platform="codeforces", external_id=f"{uid}-{p.id}-{days_ago}-{n}-{verdict}", problem_ref=p.external_id, problem_id=p.id, verdict=verdict,
                      submitted_at=NOW - timedelta(days=days_ago, minutes=n), provenance=prov))


@pytest.fixture()
def uid(client):
    register(client)
    with dbmod.SessionLocal() as db:
        return db.scalar(select(User.id))


def test_level_curve_is_monotone_and_smooth():
    prev = 0
    for xp in range(0, 5000, 50):
        lvl, into, need = g.level_for(xp)
        assert lvl >= prev and 0 <= into < need
        prev = lvl
    assert g.level_for(0)[0] == 1 and g.level_for(100)[0] == 2


def test_xp_is_awarded_once_per_problem_by_tier_and_repeat_ac_farms_nothing(client, uid):
    with dbmod.SessionLocal() as db:
        e, m, h = mk(db, "1A", 900), mk(db, "2A", 1500), mk(db, "3A", 2200)
        for p in (e, m, h):
            for k in range(5): sub(db, uid, p, "AC", 3, k)  # five ACs each: still one award
        sub(db, uid, e, "WA", 5)
        db.commit()
        ev = g.xp_events(db, uid)
    first = [x["xp"] for x in ev if x["reason"].startswith("first solve")]
    assert sorted(first) == [10, 25, 60]


def test_unverified_solves_earn_half_and_self_report_is_counted_once(client, uid):
    with dbmod.SessionLocal() as db:
        a, b = mk(db, "1A", 1500), mk(db, "2A", 1500)
        sub(db, uid, a, "AC", 2, prov="user_imported")
        db.add(ProblemStatus(user_id=uid, problem_id=b.id, solved=True, attempts=1, provenance="self_reported", updated_at=NOW - timedelta(days=1)))
        db.commit()
        ev = [x for x in g.xp_events(db, uid) if x["reason"].startswith("first solve")]
    assert sorted(x["xp"] for x in ev) == [12, 12] and all("unverified" in x["reason"] for x in ev)


def test_streak_bonus_is_capped_and_daily_challenge_xp(client, uid):
    with dbmod.SessionLocal() as db:
        ps = [mk(db, f"{i}A", 900) for i in range(12)]
        for i, p in enumerate(ps): sub(db, uid, p, "AC", 11 - i)  # 12 consecutive days
        ch = DailyChallenge(user_id=uid, day=TODAY, mode="personalized", problem_id=ps[0].id, status="completed", feedback={"solved": True, "editorial_viewed": False}, completed_at=NOW)
        ch2 = DailyChallenge(user_id=uid, day=TODAY - timedelta(days=1), mode="revision", problem_id=ps[1].id, status="completed", feedback={}, completed_at=NOW)
        db.add_all([ch, ch2]); db.commit()
        ev = g.xp_events(db, uid)
    streak = [x["xp"] for x in ev if x["reason"].startswith("streak")]
    assert max(streak) == 7 and len(streak) == 11
    assert 30 in [x["xp"] for x in ev if "daily" in x["reason"]] and 15 in [x["xp"] for x in ev if "revision" in x["reason"]]


def test_badges_require_real_evidence_and_show_progress(client, uid):
    with dbmod.SessionLocal() as db:
        ps = [mk(db, f"{i}A", 900) for i in range(3)]
        for i, p in enumerate(ps): sub(db, uid, p, "AC", i)
        db.commit()
        bs = {b["id"]: b for b in g.badges(db, uid, g.xp_events(db, uid))}
    assert bs["first-solve"]["earned"] and bs["streak-3"]["earned"] and not bs["streak-7"]["earned"] and bs["streak-7"]["progress"] == 3
    assert bs["streak-7"]["evidence"] is None and not bs["century"]["earned"] and bs["century"]["progress"] == 3


def test_comeback_badge_needs_a_14_day_gap(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 900)
        sub(db, uid, p, "WA", 30); sub(db, uid, p, "AC", 2)
        db.commit()
        assert {b["id"]: b for b in g.badges(db, uid, [])}["comeback"]["earned"]


def test_goals_progress_counts_todays_and_this_weeks_first_solves(client, uid):
    with dbmod.SessionLocal() as db:
        a, b = mk(db, "1A", 900), mk(db, "2A", 900)
        sub(db, uid, a, "AC", 0); sub(db, uid, b, "AC", 2)  # 2 days ago = Saturday (previous week) since TODAY is Monday
        db.commit()
        gl = g.goals(db, uid, g.xp_events(db, uid), None, TODAY)
    assert gl["daily"] == {"target": 1, "progress": 1} and gl["weekly"]["progress"] == 1


def test_weekly_challenge_targets_weakest_measurable_pattern_and_tracks_progress(client, uid):
    with dbmod.SessionLocal() as db:
        dps = [mk(db, f"d{i}", 1000 + i * 100, ("greedy",)) for i in range(5)]
        for i, p in enumerate(dps[:3]):
            for k in range(2): sub(db, uid, p, "WA", 20, k + i * 2)
        sub(db, uid, dps[3], "AC", 0)  # one solve in the pattern THIS week (TODAY is a Monday)
        db.commit()
        wc = g.weekly_challenge(db, uid, TODAY)
    assert wc and wc["pattern"] == "greedy" and wc["target"] == 2 and wc["progress"] == 1 and "mastery score" in wc["text"] and wc["prerequisite_for"] is None


def test_weekly_challenge_redirects_to_a_measurable_prerequisite(client, uid):
    with dbmod.SessionLocal() as db:
        dps = [mk(db, f"d{i}", 1000, ("dp",)) for i in range(3)]
        for i, p in enumerate(dps):
            for k in range(2): sub(db, uid, p, "WA", 20, k + i * 2)
        db.commit()
        wc = g.weekly_challenge(db, uid, TODAY)
    assert wc["pattern"] == "recursion" and wc["prerequisite_for"] == "Dynamic programming (foundations)" and "prerequisite" in wc["text"]


def test_leaderboard_is_opt_in_and_never_leaks_non_participants(client, uid):
    t2 = register(client, "b@example.com")
    with dbmod.SessionLocal() as db:
        u2 = db.scalars(select(User).order_by(User.id)).all()[1].id
        a, b = mk(db, "1A", 2200), mk(db, "2A", 900)
        sub(db, uid, a, "AC", 0); sub(db, u2, b, "AC", 0); db.commit()
    h1 = auth(client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    assert client.get("/gamification/leaderboard", headers=h1).json()["entries"] == []  # nobody opted in
    client.put("/me/prefs", headers=h1, json={"leaderboard_visible": True})
    d = client.get("/gamification/leaderboard", headers=h1).json()
    assert len(d["entries"]) == 1 and d["entries"][0]["you"] and d["participants"] == 1
    d2 = client.get("/gamification/leaderboard", headers=auth(t2)).json()
    assert d2["you"] is None and len(d2["entries"]) == 1 and "b@example.com" not in str(d2)


def test_api_profile_shape_goals_prefs_validation_and_auth(client, uid):
    assert client.get("/gamification/me").status_code == 401
    h = auth(client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    d = client.get("/gamification/me", headers=h).json()
    assert d["level"] == 1 and d["xp"] == 0 and d["badges_earned"] == 0 and d["weekly_challenge"] is None and "first_ac" in d["rules"]
    assert client.put("/me/prefs", headers=h, json={"daily_goal": 3, "weekly_goal": 10}).json()["daily_goal"] == 3
    assert client.get("/gamification/me", headers=h).json()["goals"]["daily"]["target"] == 3
    assert client.put("/me/prefs", headers=h, json={"daily_goal": 0}).status_code == 422
