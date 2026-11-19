from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core import db as dbmod
from app.core.config import get_settings
from app.models.ai import RecommendationLog, UserPrefs
from app.models.catalog import Problem
from app.models.daily import DailyChallenge
from app.models.integrations import Submission
from app.models.user import User
from app.services import daily, experiment
from tests.conftest import auth, register
from tests.test_daily import D, mk, sub, world  # noqa

NOW = datetime.combine(D, datetime.min.time(), UTC) + timedelta(hours=12)


def test_wilson_interval_basics():
    assert experiment.wilson(0, 0) is None
    p, lo, hi = experiment.wilson(30, 100)
    assert p == 0.3 and lo < 0.3 < hi and 0.2 < lo and hi < 0.4
    assert experiment.wilson(0, 10)[1] == 0.0


def test_assignment_is_deterministic_and_respects_fraction():
    arms = [experiment.assign_arm(u, 0.2, "s") for u in range(2000)]
    assert arms == [experiment.assign_arm(u, 0.2, "s") for u in range(2000)]
    assert 0.15 < arms.count("control") / 2000 < 0.25
    assert set(experiment.assign_arm(u, 0.0) for u in range(100)) == {"treatment"} and set(experiment.assign_arm(u, 1.0) for u in range(100)) == {"control"}


def test_control_arm_gets_baseline_policy_and_is_logged(client, world, monkeypatch):
    monkeypatch.setenv("CODEMIND_EXPERIMENT_HOLDOUT_FRACTION", "1.0"); get_settings.cache_clear()
    try:
        with dbmod.SessionLocal() as db:
            ch = daily.generate(db, world["a"], D)
            assert ch.policy_version == "baseline-rating-matched-v1" and ch.explanation["top_objectives"] == []
            lg = db.scalar(select(RecommendationLog))
            assert lg.arm == "control" and lg.in_analysis and lg.challenge_id == ch.id and lg.est_rating
    finally:
        get_settings.cache_clear()


def test_opt_out_always_gets_full_policy_and_is_excluded(client, world, monkeypatch):
    monkeypatch.setenv("CODEMIND_EXPERIMENT_HOLDOUT_FRACTION", "1.0"); get_settings.cache_clear()
    try:
        with dbmod.SessionLocal() as db:
            db.add(UserPrefs(user_id=world["a"], experiment_opt_out=True)); db.commit()
            ch = daily.generate(db, world["a"], D)
            lg = db.scalar(select(RecommendationLog))
            assert ch.policy_version == "daily-v1" and lg.arm == "treatment" and lg.in_analysis is False
    finally:
        get_settings.cache_clear()


def test_non_personalised_modes_never_use_the_control_baseline(client, world, monkeypatch):
    monkeypatch.setenv("CODEMIND_EXPERIMENT_HOLDOUT_FRACTION", "1.0"); get_settings.cache_clear()
    try:
        with dbmod.SessionLocal() as db:
            ch = daily.generate(db, world["b"], D, "cp")
            assert ch.policy_version == "daily-v1" and db.scalar(select(RecommendationLog)).in_analysis is False
    finally:
        get_settings.cache_clear()


def test_report_refuses_claims_below_minimum_sample(client, world):
    with dbmod.SessionLocal() as db:
        daily.generate(db, world["a"], D)
        r = experiment.report(db, NOW)
    assert r["claims_allowed"] is False and r["comparison"] is None and "No effect is claimed" in r["message"] and r["arms"]["treatment"]["n"] == 1


def test_report_compares_arms_with_intervals_when_enough_data_and_uses_verified_solves(client):
    register(client)
    with dbmod.SessionLocal() as db:
        uid = db.scalar(select(User.id))
        base = NOW - timedelta(days=20)
        for i in range(70):
            p = mk(db, f"e{i}", 1000, ("dp",)); arm = "treatment" if i < 35 else "control"
            ch = DailyChallenge(user_id=uid, day=(base + timedelta(days=i % 5)).date(), mode="personalized", problem_id=p.id, primary_pattern="dynamic-programming", status="completed" if i % 2 == 0 else "assigned")
            db.add(ch); db.flush()
            db.add(RecommendationLog(user_id=uid, challenge_id=ch.id, problem_id=p.id, arm=arm, policy="x", pattern="dynamic-programming", est_rating=1000, created_at=base))
            if (arm == "treatment" and i % 3 != 0) or (arm == "control" and i % 6 == 0):  # treatment solves more, by construction of the fixture
                db.add(Submission(user_id=uid, platform="codeforces", external_id=f"v{i}", problem_ref=p.external_id, problem_id=p.id, verdict="AC", submitted_at=base + timedelta(days=1), provenance="verified"))
        db.commit()
        r = experiment.report(db, NOW)
    assert r["claims_allowed"] and r["arms"]["treatment"]["n"] == 35 and r["arms"]["control"]["n"] == 35
    t, c = r["arms"]["treatment"]["verified_solve_rate"][0], r["arms"]["control"]["verified_solve_rate"][0]
    assert t > c and r["comparison"]["verified_solve_rate_diff"][1] > 0  # CI excludes zero in this constructed case
    assert r["arms"]["treatment"]["matured_with_delta"] >= 0 and "Observational" in r["design"]["limits"]


def test_unverified_or_earlier_submissions_do_not_count_as_verified_solves(client):
    register(client)
    with dbmod.SessionLocal() as db:
        uid = db.scalar(select(User.id)); at = NOW - timedelta(days=3)
        p1, p2, p3 = mk(db, "a1", 900, ("math",)), mk(db, "a2", 900, ("math",)), mk(db, "a3", 900, ("math",))
        for p in (p1, p2, p3):
            ch = DailyChallenge(user_id=uid, day=at.date(), mode="personalized", problem_id=p.id, status="assigned"); db.add(ch); db.flush()
            db.add(RecommendationLog(user_id=uid, challenge_id=ch.id, problem_id=p.id, arm="treatment", policy="x", created_at=at))
        db.add(Submission(user_id=uid, platform="codeforces", external_id="s1", problem_ref="a1", problem_id=p1.id, verdict="AC", submitted_at=at - timedelta(days=1), provenance="verified"))  # before assignment
        db.add(Submission(user_id=uid, platform="codeforces", external_id="s2", problem_ref="a2", problem_id=p2.id, verdict="AC", submitted_at=at + timedelta(hours=1), provenance="verified"))
        db.commit()
        rows = experiment.outcomes(db, NOW)
    assert [r["verified_solved"] for r in rows] == [False, True, False]


def test_verify_solves_completes_assigned_challenges_and_schedules_review(client, world):
    with dbmod.SessionLocal() as db:
        ch = daily.generate(db, world["b"], D)
        sub(db, world["b"], db.get(Problem, ch.problem_id), "AC", days_ago=-1)
        db.commit()
        # make the challenge "created" before the submission
        ch.created_at = NOW - timedelta(days=2); db.commit()
        assert daily.verify_solves(db, world["b"], NOW) == 1
        db.refresh(ch)
        assert ch.status == "completed" and ch.feedback["verified"] and ch.feedback["auto"]
        assert daily.verify_solves(db, world["b"], NOW) == 0  # idempotent


def test_admin_report_endpoint_and_prefs(client):
    t = register(client)
    h = auth(t)
    assert client.put("/me/prefs", headers=h, json={"experiment_opt_out": True}).json()["experiment_opt_out"] is True
    assert client.put("/me/prefs", headers=h, json={"email_notifications": True}).json()["email_notifications"] is True
    assert client.get("/admin/experiments/daily", headers=h).status_code == 403
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User)); u.role = "admin"; db.commit()
    assert client.get("/admin/experiments/daily", headers=h).json()["claims_allowed"] is False
