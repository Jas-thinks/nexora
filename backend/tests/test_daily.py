"""Daily Challenge tests. Fixtures are SYNTHETIC (clearly: built in-test), used to prove behaviour, not to claim quality."""
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.models.catalog import Problem, ProblemStatus, Sheet, SheetItem
from app.models.daily import DailyChallenge, ReviewItem
from app.models.integrations import Submission
from app.models.user import User
from app.services import daily, recommender
from tests.conftest import auth, register

D = date(2026, 6, 1)


def mk(db, ext, rating, tags, plat="codeforces"):
    p = Problem(platform=plat, external_id=ext, name=f"P{ext}", rating=rating, tags=tags, url=f"https://x/{ext}", canonical_url=f"https://x/{ext}")
    db.add(p); db.flush(); return p


def sub(db, uid, p, verdict, days_ago=1, n=0):
    db.add(Submission(user_id=uid, platform=p.platform, external_id=f"s{uid}-{p.id}-{n}-{verdict}", problem_ref=p.external_id, problem_id=p.id,
                      verdict=verdict, submitted_at=datetime.combine(D, datetime.min.time(), UTC) - timedelta(days=days_ago, minutes=n)))


@pytest.fixture()
def world(client):
    """Catalog with binary search / dp / graph problems across ratings, plus two users with different histories."""
    register(client, "a@example.com"); register(client, "b@example.com")
    with dbmod.SessionLocal() as db:
        probs = {}
        i = 0
        for tag in ("binary search", "dp", "graphs", "greedy", "math"):
            for r in range(800, 2000, 100):
                i += 1
                probs[(tag, r)] = mk(db, f"{i}A", r, [tag])
        db.commit()
        a, b = db.scalars(select(User).order_by(User.id)).all()
        # user A: solved lots of binary search, failing dp repeatedly
        for r in range(800, 1300, 100):
            sub(db, a.id, probs[("binary search", r)], "AC", 5)
        for k, r in enumerate((900, 1000, 1100)):
            sub(db, a.id, probs[("dp", r)], "WA", 3, k)
        # user B: solved graph + math, never touched dp
        for r in range(800, 1300, 100):
            sub(db, b.id, probs[("graphs", r)], "AC", 4)
            sub(db, b.id, probs[("math", r)], "AC", 4)
        db.commit()
        recommender.rebuild_mastery(db, a.id); recommender.rebuild_mastery(db, b.id)
        return {"a": a.id, "b": b.id, "probs": {k: v.id for k, v in probs.items()}}


def pat(ch): return ch.primary_pattern


def test_weak_pattern_is_targeted_and_explained_with_real_numbers(client, world):
    with dbmod.SessionLocal() as db:
        ch = daily.generate(db, world["a"], D)
        ex = ch.explanation
        assert pat(ch) == "dynamic-programming" or pat(ch).startswith("dp")  # A fails dp repeatedly, solved only binary search
        assert any("weakness" in x["objective"] for x in ex["top_objectives"])
        assert any("0 of 3" in w or "0 solved" in w or "weakness" in w.lower() for w in ex["why"] + ex["evidence"])
        assert "estimated" in ex["difficulty"] and ex["after_this"] and "policy" in ex


def test_two_students_get_different_personalised_problems(client, world):
    with dbmod.SessionLocal() as db:
        ca, cb = daily.generate(db, world["a"], D), daily.generate(db, world["b"], D)
        assert ca.problem_id != cb.problem_id and pat(ca) != pat(cb)
        assert ca.explanation["why"] != cb.explanation["why"]


def test_idempotent_per_day_and_varies_across_days(client, world):
    with dbmod.SessionLocal() as db:
        c1 = daily.generate(db, world["a"], D)
        assert daily.generate(db, world["a"], D).id == c1.id
        c2 = daily.generate(db, world["a"], D + timedelta(days=1))
        assert c2.problem_id != c1.problem_id  # recent daily problems are excluded


def test_never_recommends_solved_problems(client, world):
    with dbmod.SessionLocal() as db:
        solved = {pid for (pid,) in db.execute(select(Submission.problem_id).where(Submission.user_id == world["a"], Submission.verdict == "AC"))}
        for k in range(8):
            assert daily.generate(db, world["a"], D + timedelta(days=k)).problem_id not in solved


def test_diversity_avoids_same_pattern_every_day(client, world):
    with dbmod.SessionLocal() as db:
        pats = [pat(daily.generate(db, world["b"], D + timedelta(days=k))) for k in range(6)]
        assert len(set(pats)) >= 2


def test_cold_start_is_gentle_and_says_so(client):
    register(client, "new@example.com")
    with dbmod.SessionLocal() as db:
        for tag in ("math", "greedy"):
            for r in range(800, 1600, 100):
                mk(db, f"{tag}{r}", r, [tag])
        db.commit()
        uid = db.scalar(select(User.id))
        ch = daily.generate(db, uid, D)
        p = db.get(Problem, ch.problem_id)
        assert p.rating <= 900, "a brand-new student must not receive a hard problem"
        assert any("starting gently" in w for w in ch.explanation["why"])


def test_difficulty_paths_shift_difficulty(client, world):
    with dbmod.SessionLocal() as db:
        easy = db.get(Problem, daily.generate(db, world["b"], D, "personalized", "beginner").problem_id).rating
        hard = db.get(Problem, daily.generate(db, world["b"], D, "cp", "advanced").problem_id).rating
        assert hard > easy


def test_topic_mode_stays_on_topic(client, world):
    with dbmod.SessionLocal() as db:
        ch = daily.generate(db, world["b"], D, "topic", None, "binary-search")
        assert "binary search" in db.get(Problem, ch.problem_id).tags


def test_interview_mode_only_uses_sheet_problems(client, world):
    with dbmod.SessionLocal() as db:
        lc = mk(db, "two-sum", None, [], "leetcode"); lc.source_difficulty = "Easy"
        sh = Sheet(slug="s", title="s", owner_id=None); db.add(sh); db.flush()
        db.add(SheetItem(sheet_id=sh.id, problem_id=lc.id, section="Arrays & Hashing", position=0)); db.commit()
        ch = daily.generate(db, world["b"], D, "interview")
        assert ch.problem_id == lc.id
        assert ch.explanation["difficulty"].startswith("Source difficulty")


def test_validation_errors(client, world):
    with dbmod.SessionLocal() as db:
        for kw in ({"mode": "nope"}, {"path": "x"}, {"mode": "topic"}, {"topic": "not-a-pattern"}):
            with pytest.raises(ValueError):
                daily.generate(db, world["a"], D, **{"mode": "personalized", **kw})


def test_revision_mode_needs_due_items_then_serves_them(client, world):
    with dbmod.SessionLocal() as db:
        with pytest.raises(LookupError):
            daily.generate(db, world["a"], D, "revision")
        pid = world["probs"][("binary search", 800)]
        db.add(ReviewItem(user_id=world["a"], problem_id=pid, due_at=datetime.combine(D, datetime.min.time(), UTC) - timedelta(days=1), box=1))
        db.commit()
        ch = daily.generate(db, world["a"], D, "revision")
        assert ch.problem_id == pid and "review is due" in ch.explanation["why"][0]


def test_feedback_loop_hard_challenge_makes_next_pick_easier_in_that_pattern(client, world):
    with dbmod.SessionLocal() as db:
        uid = world["b"]
        c1 = daily.generate(db, uid, D, "topic", None, "greedy")
        r1 = db.get(Problem, c1.problem_id).rating
        daily.complete(db, c1, solved=False, hints_used=4, editorial_viewed=True, self_difficulty=5)
        c2 = daily.generate(db, uid, D + timedelta(days=1), "topic", None, "greedy")
        assert db.get(Problem, c2.problem_id).rating < r1 or r1 == 800


def test_complete_updates_progress_mastery_and_schedules_review(client, world):
    with dbmod.SessionLocal() as db:
        uid = world["b"]
        ch = daily.generate(db, uid, D)
        daily.complete(db, ch, solved=True, hints_used=0, self_difficulty=3, understanding=4)
        st = db.scalar(select(ProblemStatus).where(ProblemStatus.user_id == uid, ProblemStatus.problem_id == ch.problem_id))
        rv = db.scalar(select(ReviewItem).where(ReviewItem.user_id == uid, ReviewItem.problem_id == ch.problem_id))
        assert st.solved and rv.box == 1 and ch.status == "completed"
        daily.complete(db, daily.generate(db, uid, D + timedelta(days=1)), solved=False)  # failure => review tomorrow (box 0)
        assert db.scalars(select(ReviewItem).order_by(ReviewItem.id.desc())).first().box == 0


def test_swap_once_per_day_and_never_same_problem(client, world):
    with dbmod.SessionLocal() as db:
        c = daily.generate(db, world["b"], D)
        old = c.problem_id
        n = daily.swap(db, c, "too long")
        assert n.problem_id != old and n.swaps == 1 and c.status == "swapped"
        with pytest.raises(PermissionError):
            daily.swap(db, n, "again")
        assert db.scalar(select(DailyChallenge).where(DailyChallenge.user_id == world["b"], DailyChallenge.day == D, DailyChallenge.status == "assigned")).id == n.id


# ----------------------------------------------------------------------------- API
def login(client, email):
    return auth(client.post("/auth/login", json={"email": email, "password": "correct-horse-battery"}).json())


def test_api_flow_and_authorization(client, world):
    ha, hb = login(client, "a@example.com"), login(client, "b@example.com")
    r = client.get("/daily", headers=ha)
    assert r.status_code == 200
    d = r.json()
    assert d["problem"]["url"] and "Metadata" in d["problem"]["provenance"] and d["explanation"]["why"]
    assert d["hints"][0]["level"] == 1 and d["hints"][-1]["unavailable"]  # no fabricated problem-specific hints
    assert client.post(f"/daily/{d['id']}/complete", headers=hb, json={"solved": True}).status_code == 404  # not B's challenge
    assert client.post(f"/daily/{d['id']}/complete", headers=ha, json={"solved": True, "self_difficulty": 9}).status_code == 422
    ok = client.post(f"/daily/{d['id']}/complete", headers=ha, json={"solved": True, "hints_used": 1, "understanding": 4})
    assert ok.status_code == 200 and ok.json()["status"] == "completed"
    assert client.post(f"/daily/{d['id']}/complete", headers=ha, json={"solved": True}).status_code == 409
    h = client.get("/daily/history", headers=ha).json()
    assert h["completed"] == 1 and client.get("/daily?mode=bogus", headers=ha).status_code == 422
    assert client.get("/daily").status_code == 401


def test_pattern_endpoints(client, world):
    ha = login(client, "a@example.com")
    t = client.get("/patterns", headers=ha).json()
    assert t["review_status"] == "unreviewed" and t["count"] > 80
    cov = client.get("/patterns/coverage", headers=ha).json()
    by = {p["id"]: p for p in cov["patterns"]}
    assert by["binary-search"]["status"] in ("practised", "mastered", "learning") and by["dynamic-programming"]["status"] == "weak"
    assert by["segment-tree"]["status"] == "unexplored"
    d = client.get("/patterns/binary-search-answer", headers=ha).json()
    assert "binary-search" in d["contrasts_with"] and d["learning_page"]["status"] == "outline"
    assert client.get("/patterns/nope", headers=ha).status_code == 404
    mastery_a = client.get("/patterns/dynamic-programming", headers=ha).json()["mastery"]
    assert mastery_a["status"] == "weak" and mastery_a["reasons"]


def test_unmeasured_prereqs_are_never_reported_as_gaps(client, world):
    from app.patterns import mastery as m
    with dbmod.SessionLocal() as db:
        st = m.assess_all(db, world["a"])
        assert st["modular-arithmetic"].status == "unmeasured"
        assert st["modular-arithmetic"].status == "unmeasured"
        assert "modular-arithmetic" not in st["number-theory"].missing_prereqs + st["combinatorics"].missing_prereqs
        cov = m.coverage(st)
        assert cov["by_status"].get("unmeasured", 0) > 0


def test_assessment_cache_hits_then_invalidates_on_new_evidence_and_catalog_change(client, world):
    from app.patterns import mastery as m
    with dbmod.SessionLocal() as db:
        uid = world["a"]
        a1 = m.assess_cached(db, uid)
        assert m.assess_cached(db, uid) is a1  # served from cache
        before = a1["dynamic-programming"].solved
        sub(db, uid, db.get(Problem, world["probs"][("dp", 1500)]), "AC", days_ago=0, n=99); db.commit()
        a2 = m.assess_cached(db, uid)
        assert a2 is not a1 and a2["dynamic-programming"].solved == before + 1  # new submission => recomputed
        m.bump_catalog()
        assert m.assess_cached(db, uid) is not a2  # catalog write => recomputed


def test_cold_start_challenge_refreshes_after_real_evidence_arrives_but_warm_ones_stay(client):
    register(client, "late@example.com")
    with dbmod.SessionLocal() as db:
        probs = [mk(db, f"c{r}", r, ["math"]) for r in range(800, 1800, 100)] + [mk(db, f"g{r}", r, ["greedy"]) for r in range(800, 1800, 100)]
        db.commit()
        uid = db.scalar(select(User.id))
        first = daily.generate(db, uid, D)
        assert first.objective_scores["cold"] is True
        for i, p in enumerate(probs[:8]):  # the student now syncs 8 verified solves
            sub(db, uid, p, "AC", days_ago=2, n=i)
        db.commit()
        second = daily.generate(db, uid, D)
        assert second.id != first.id and not second.objective_scores["cold"]
        assert db.get(DailyChallenge, first.id).status == "swapped"
        assert daily.generate(db, uid, D).id == second.id  # warm => stable for the rest of the day
