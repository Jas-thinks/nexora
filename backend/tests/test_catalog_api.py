from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.integrations.source_matrix import BY_SLUG, COLS, MATRIX
from app.models.catalog import Problem, ProblemStatisticsSnapshot, SyncCheckpoint, SyncFailure
from app.models.integrations import Contest
from app.models.user import User
from tests.conftest import auth, register


@pytest.fixture()
def env(client):
    t = register(client)
    with dbmod.SessionLocal() as db:
        db.add_all([
            Problem(platform="codeforces", external_id="1A", name="A", rating=800, tags=["math"], url="u", canonical_url="u", contest_ref="1", problem_index="A", solved_count=10, submission_count=20, source="t", source_record={"x": 1}),
            Problem(platform="codeforces", external_id="2B", name="B", rating=None, tags=[], url="u2", canonical_url="u2", status="missing_upstream"),
            Problem(platform="atcoder", external_id="abc1_a", name="C", rating=None, tags=[], url="u3", canonical_url="u3", source_difficulty="est. difficulty 100", solved_count=5)])
        db.add(Contest(platform="codeforces", external_id="1", name="Round 1", start_time=datetime(2010, 1, 1, tzinfo=UTC), url="c", source="t"))
        db.flush()
        db.add(ProblemStatisticsSnapshot(problem_id=1, source="t", solved_count=10, submission_count=20))
        db.add(SyncCheckpoint(platform="codeforces", stage="enumerate", done=True, discovered=3, retrieved=3))
        db.add(SyncFailure(platform="codeforces", stage="enumerate", ref="p3", error="boom"))
        db.commit()
    return client, auth(t)


def test_matrix_is_internally_honest():
    slugs = [m["slug"] for m in MATRIX]
    assert len(slugs) == len(set(slugs)) and len(slugs) >= 40
    for m in MATRIX:
        assert all(m[c] in ("Supported", "Partial", "Unavailable") for c in COLS)
        assert m["official_api"] in ("Available", "Not available", "Unverified") and m["data_rights"] in ("Verified", "Restricted", "Unclear")
        assert m["evidence"] and m["verified_on"]
        if any(m[c] == "Supported" for c in COLS):
            assert m["adapter"], f"{m['slug']} claims Supported without an adapter"
    # every seed from the directive is present
    for seed in ("codeforces", "codechef", "leetcode", "atcoder", "geeksforgeeks", "hackerrank", "hackerearth", "topcoder", "codesignal", "cses", "spoj", "kattis", "dmoj", "timus",
                 "projecteuler", "toph", "csacademy", "uva", "lightoj", "usaco", "aizu", "yukicoder", "luogu", "omegaup", "beecrowd", "tlx", "quera", "eolymp", "france-ioi", "kilonova",
                 "szkopul", "infoarena", "neps", "ksp", "codeup", "mendo", "icpc", "ubc", "clist", "cf-gym", "google-cc", "rosalind"):
        assert seed in BY_SLUG, f"seed {seed} silently omitted"
    # robots-disallowed APIs must not be marked usable
    for s in ("hackerrank", "omegaup", "kilonova"):
        assert BY_SLUG[s]["listing"] == "Unavailable"


def test_sources_endpoint_reports_counts_completeness_and_failures(env):
    c, h = env
    d = c.get("/sources", headers=h).json()
    cf = next(s for s in d["sources"] if s["slug"] == "codeforces")
    assert cf["records"]["records"] == 2 and cf["records"]["missing_upstream"] == 1
    assert cf["records"]["completeness"]["rating"] == 50.0 and cf["sync"]["done"] and cf["unresolved_failures"] == 1 and cf["can_backfill"]
    assert next(s for s in d["sources"] if s["slug"] == "leetcode")["records"] is None  # no data => null, not 0%
    assert d["totals"]["platform_records"] == 3 and d["totals"]["unresolved_failures"] == 1 and "No source is claimed complete" in d["note"]
    assert c.get("/sources").status_code == 401


def test_problem_detail_has_provenance_contest_stats_and_no_statement(env):
    c, h = env
    d = c.get("/problems/1", headers=h).json()
    assert d["contest"]["name"] == "Round 1" and d["statistics"]["history"][0]["solved_count"] == 10
    assert d["provenance"]["raw_record_preserved"] and d["provenance"]["statement_access"] == "link_only" and "statement" not in {k for k in d}
    assert "not comparable" in d["difficulty"]["note"]
    assert c.get("/problems/999", headers=h).status_code == 404


def test_catalog_analytics_uses_persisted_data_without_mixing_scales(env):
    c, h = env
    a = c.get("/analytics/catalog", headers=h).json()
    assert a["problems_per_platform"] == {"codeforces": 2, "atcoder": 1}
    assert a["codeforces_rating_distribution"] == {"800": 1} and ("math", 1) in [tuple(x) for x in a["top_tags"]]
    assert a["codeforces_problems_per_contest_year"] == {"2010": 1}
    assert "never ranked" in a["note"]


def test_backfill_admin_only_and_rejects_unsupported(env):
    c, h = env
    assert c.post("/admin/backfill/codechef", headers=h).status_code == 403
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User)); u.role = "admin"; db.commit()
    h2 = auth(c.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json())
    assert c.post("/admin/backfill/codechef", headers=h2).status_code == 202
    r = c.post("/admin/backfill/leetcode", headers=h2)
    assert r.status_code == 422 and "No problem-source adapter" in r.json()["detail"]
