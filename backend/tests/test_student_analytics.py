"""Analytics tests use SYNTHETIC events built in-test to verify the maths and the 'unknown is not zero' rules."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.models.catalog import Problem
from app.models.integrations import RatingHistory, Submission
from app.models.user import User
from app.services import student_analytics as sa
from tests.conftest import auth, register

NOW = datetime(2026, 6, 15, 12, tzinfo=UTC)


def mk(db, ext, rating, tags=("dp",)):
    p = Problem(platform="codeforces", external_id=ext, name=f"P{ext}", rating=rating, tags=list(tags), url="u", canonical_url="u")
    db.add(p); db.flush(); return p


def sub(db, uid, p, verdict, day_offset, n=0, lang="C++17", in_contest=None, prov="verified", platform="codeforces"):
    db.add(Submission(user_id=uid, platform=platform, external_id=f"{uid}-{p.id if p else 'x'}-{day_offset}-{n}-{verdict}", problem_ref=p.external_id if p else "zz", problem_id=p.id if p else None,
                      verdict=verdict, submitted_at=NOW - timedelta(days=day_offset, minutes=n), language=lang, in_contest=in_contest, provenance=prov))


@pytest.fixture()
def uid(client):
    register(client)
    with dbmod.SessionLocal() as db:
        return db.scalar(select(User.id))


def test_empty_user_gets_none_not_zero(client, uid):
    with dbmod.SessionLocal() as db:
        r = sa.compute(db, uid, "90d", NOW)
    assert r["empty"] and r["summary"]["acceptance_rate"] is None and r["summary"]["consistency"] is None
    assert r["next_best_action"][0]["href"] == "/connections"


def test_summary_streak_acceptance_and_first_try(client, uid):
    with dbmod.SessionLocal() as db:
        a, b, c = mk(db, "1A", 800), mk(db, "2A", 1000), mk(db, "3A", 1200)
        sub(db, uid, a, "AC", 0); sub(db, uid, b, "WA", 1, 1); sub(db, uid, b, "AC", 1, 0); sub(db, uid, c, "WA", 2); sub(db, uid, c, "WA", 3)
        db.commit()
        r = sa.compute(db, uid, "30d", NOW)
    s = r["summary"]
    assert s["submissions"] == 5 and s["accepted"] == 2 and s["acceptance_rate"] == 0.4
    assert s["solved"] == 2 and s["attempted_problems_all_time"] == 3
    assert s["streak"] == 4 and s["longest_streak"] == 4  # days 0,1,2,3 all active
    assert s["first_try_rate"] == pytest.approx(1 / 3, abs=1e-3)  # only problem A solved on first submission
    assert s["consistency"] == pytest.approx(4 / 30, abs=1e-3)


def test_range_filters_and_heatmap_ignores_range(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 800)
        sub(db, uid, p, "AC", 2); sub(db, uid, p, "WA", 200)
        db.commit()
        r30, rall = sa.compute(db, uid, "30d", NOW), sa.compute(db, uid, "all", NOW)
    assert r30["summary"]["submissions"] == 1 and rall["summary"]["submissions"] == 2
    assert len(r30["heatmap"]) == 2  # heatmap is the fixed last-365-days view
    with pytest.raises(ValueError):
        with dbmod.SessionLocal() as db:
            sa.compute(db, uid, "forever", NOW)


def test_unknown_contest_flag_is_excluded_not_counted_as_practice(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 800)
        for i in range(6): sub(db, uid, p, "AC" if i % 2 else "WA", 1, i, in_contest=True)
        for i in range(6): sub(db, uid, p, "AC", 2, i, in_contest=False)
        for i in range(4): sub(db, uid, p, "WA", 3, i, in_contest=None)
        db.commit()
        r = sa.compute(db, uid, "30d", NOW)
    ca = r["contest_accuracy"]
    assert ca["in_contest"]["n"] == 6 and ca["practice"]["n"] == 6 and ca["unknown_excluded"] == 4
    assert ca["in_contest"]["acceptance"] == 0.5 and ca["practice"]["acceptance"] == 1.0


def test_contest_accuracy_withheld_when_too_little_known_data(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 800)
        for i in range(5): sub(db, uid, p, "AC", 1, i, in_contest=None)
        db.commit()
        assert sa.compute(db, uid, "30d", NOW)["contest_accuracy"] is None


def test_rating_history_stats_and_missing_fields_stay_none(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 800); sub(db, uid, p, "AC", 1)
        old = 1000
        for i, new in enumerate((1100, 1050, 1200, 1150, 1300)):
            db.add(RatingHistory(user_id=uid, platform="codeforces", contest_ref=str(i), contest_name=f"R{i}", at=NOW - timedelta(days=50 - i), old_rating=old, new_rating=new, rank=100 + i))
            old = new
        db.commit()
        r = sa.compute(db, uid, "90d", NOW)["ratings"]["codeforces"]
    assert r["current"] == 1300 and r["peak"] == 1300 and r["contests"] == 5 and r["median_rank"] == 102
    assert r["median_performance"] is None and r["volatility"] is not None  # CF exposes no performance => None


def test_improvement_needs_enough_data_and_labels_direction(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 800)
        for i in range(15): sub(db, uid, p, "WA", 20 - i // 2, i)       # early: all fail
        for i in range(15): sub(db, uid, p, "AC", 5 - i // 5, i)         # late: all pass
        db.commit()
        imp = sa.compute(db, uid, "90d", NOW)["improvement"]
    assert imp["verdict"] == "improving" and imp["acceptance_delta"] > 0.5
    with dbmod.SessionLocal() as db:
        db.query(Submission).delete(); p = db.scalar(select(Problem))
        for i in range(8): sub(db, uid, p, "AC", 2, i)
        db.commit()
        assert sa.compute(db, uid, "90d", NOW)["improvement"] is None  # < 20 submissions => no claim


def test_abandoned_and_repeated_failure_detection(client, uid):
    with dbmod.SessionLocal() as db:
        old, recent, solved = mk(db, "1A", 1500), mk(db, "2A", 1500), mk(db, "3A", 1500)
        for i in range(3): sub(db, uid, old, "WA", 40, i)
        for i in range(4): sub(db, uid, recent, "TLE", 3, i)
        for i in range(3): sub(db, uid, solved, "WA", 5, i)
        sub(db, uid, solved, "AC", 4)
        db.commit()
        r = sa.compute(db, uid, "90d", NOW)
    assert [x["name"] for x in r["abandoned"]["examples"]] == ["P1A"] and [x["name"] for x in r["repeated_failures"]["examples"]] == ["P2A"]


def test_topics_need_five_problems_and_report_trend(client, uid):
    with dbmod.SessionLocal() as db:
        ps = [mk(db, f"{i}A", 1000, ("greedy",)) for i in range(6)]
        for i, p in enumerate(ps[:3]):
            for k in range(2): sub(db, uid, p, "WA", 60, k + i * 3)       # prior: failing
        for i, p in enumerate(ps):
            for k in range(2): sub(db, uid, p, "AC", 5, k + i * 3)        # recent: passing
        for t in ("math",):
            mk(db, "9Z", 800, (t,))
        db.commit()
        r = sa.compute(db, uid, "all", NOW)
    names = {x["topic"] for x in r["topics"]["strongest"]}
    assert "greedy" in names and "math" not in names
    assert r["topics"]["improving"] and r["topics"]["improving"][0]["topic"] == "greedy"


def test_imported_and_unlinked_are_counted_and_language_unknown_reported(client, uid):
    with dbmod.SessionLocal() as db:
        p = mk(db, "1A", 800)
        sub(db, uid, p, "AC", 1, prov="user_imported", lang=None); sub(db, uid, None, "WA", 1, 5, lang=None)
        db.commit()
        s = sa.compute(db, uid, "30d", NOW)
    assert s["summary"]["imported_submissions"] == 1 and s["summary"]["unlinked_submissions"] == 1 and s["language_unknown"] == 2 and s["languages"] == {}


def test_api_auth_validation_and_isolation(client, uid):
    t = register(client, "b@example.com")
    assert client.get("/analytics/me").status_code == 401
    assert client.get("/analytics/me?range=bad", headers=auth(t)).status_code == 422
    r = client.get("/analytics/me?range=30d", headers=auth(t)).json()
    assert r["empty"] is True  # user B sees none of user A's data
