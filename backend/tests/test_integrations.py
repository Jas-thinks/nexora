import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.core import db as dbmod
from app.integrations import adapters as A
from app.integrations.http import FetchError, PoliteClient
from app.integrations.registry import PLATFORMS, matrix
from app.integrations.types import NotSupported
from app.models.catalog import Problem, ProblemStatus, TopicMastery
from app.models.integrations import ConnectedProfile, Contest, Submission
from app.models.user import User
from app.services import ingest
from tests.conftest import register

FX = Path(__file__).parent / "fixtures"
J = lambda n: json.loads((FX / n).read_text())


def router(overrides=None):
    routes = {
        "/api/user.info": ("cf_user_info.json", 200), "/api/user.status": ("cf_user_status.json", 200),
        "/api/user.rating": ("cf_user_rating.json", 200), "/api/contest.list": ("cf_contests.json", 200),
        "/atcoder-api/v3/user/submissions": ("ac_subs.json", 200), "/history/json": ("ac_history.json", 200),
        "/resources/contests.json": ("ac_contests.json", 200), "/resources/problems.json": ("ac_problems.json", 200),
        "/api/v2/contests": ("dmoj_contests.json", 200), "/api/v2/problems": ("dmoj_problems.json", 200),
        "/api/list/contests/all": ("cc_contests.json", 200),
    }
    routes.update(overrides or {})
    calls = []

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        for suffix, (fx, code) in routes.items():
            if req.url.path.endswith(suffix):
                body = fx if isinstance(fx, (dict, list)) else J(fx)
                return httpx.Response(code, json=body)
        if req.url.path.startswith("/users/"):
            return httpx.Response(404 if "nobody" in req.url.path else 200, text="<html/>")
        return httpx.Response(404, json={"error": "no route"})
    return httpx.MockTransport(handler), calls


def client(overrides=None):
    t, calls = router(overrides)
    return PoliteClient(min_interval=0, transport=t, sleep=lambda s: None), calls


# ------------------------------------------------------------------ registry
def test_registry_is_honest():
    m = {p["slug"]: p for p in matrix()}
    assert m["leetcode"]["status"] == "manual_import" and not m["leetcode"]["has_adapter"]
    assert m["codeforces"]["has_adapter"] and m["codeforces"]["verified_on"]
    for p in PLATFORMS:
        if p.status in ("integrated", "contests_only"):
            assert p.adapter and p.evidence, f"{p.slug} claims support without adapter+evidence"
        if p.evidence is None:  # never investigated => must not claim anything beyond manual import
            assert p.status == "link_only" and p.adapter is None
    slugs = [p.slug for p in PLATFORMS]
    assert len(set(slugs)) == len(slugs) and len(slugs) >= 35  # directive lists 40 incl. duplicates


# ------------------------------------------------------------------ Codeforces
def test_cf_normalization_and_verdicts():
    http, _ = client()
    page = A.CodeforcesAdapter(http).fetch_submissions("tourist")
    assert page.items and all(s.verdict in {"AC", "WA", "TLE", "MLE", "RE", "CE", "OTHER"} for s in page.items)
    raw = J("cf_user_status.json")["result"]
    first = next(r for r in raw if r.get("verdict") == "OK")
    n = A.CodeforcesAdapter.normalize_submission(first)
    assert n.verdict == "AC" and n.problem_ref == f"{first['problem']['contestId']}{first['problem']['index']}"
    assert n.in_contest == (first["author"]["participantType"] == "CONTESTANT")
    assert n.memory_kb == first["memoryConsumedBytes"] // 1024


def test_cf_incremental_checkpoint_returns_nothing_new():
    http, _ = client()
    ad = A.CodeforcesAdapter(http)
    p1 = ad.fetch_submissions("tourist")
    p2 = ad.fetch_submissions("tourist", p1.checkpoint)
    assert len(p1.items) > 0 and p2.items == [] and p2.checkpoint == p1.checkpoint


def test_cf_does_not_skip_past_unjudged_submission():
    data = J("cf_user_status.json")
    data["result"][5] = {**data["result"][5], "verdict": "TESTING"}
    stuck = data["result"][5]["id"]
    http, _ = client({"/api/user.status": (data, 200)})
    page = A.CodeforcesAdapter(http).fetch_submissions("tourist")
    assert page.checkpoint["last_id"] < stuck and page.skipped >= 1


def test_cf_unknown_handle_is_a_clear_error():
    http, _ = client({"/api/user.info": ({"status": "FAILED", "comment": "handles: User with handle zzz not found"}, 400)})
    with pytest.raises(FetchError, match="not found"):
        A.CodeforcesAdapter(http).validate_profile("zzz")


def test_cf_rating_and_contests():
    http, _ = client()
    ad = A.CodeforcesAdapter(http)
    r = ad.fetch_rating_history("tourist")
    assert r[0].new_rating == 1602 and r[0].at.tzinfo is not None
    cs = ad.fetch_contests()
    assert len(cs) == 6 and all(c.url.startswith("https://codeforces.com/contest/") for c in cs)


# ------------------------------------------------------------------ polite http
def test_retries_503_then_succeeds_and_honours_retry_after():
    seq = iter([httpx.Response(503), httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={"ok": 1})])
    sleeps = []
    c = PoliteClient(min_interval=0, transport=httpx.MockTransport(lambda r: next(seq)), sleep=sleeps.append)
    assert c.get_json("https://x.test/a") == {"ok": 1}
    assert 7 in sleeps


def test_gives_up_after_retries_and_marks_retryable():
    c = PoliteClient(min_interval=0, retries=2, transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None)
    with pytest.raises(FetchError) as e:
        c.get_json("https://x.test/a")
    assert e.value.retryable


def test_4xx_is_not_retried():
    n = {"c": 0}
    def h(r): n["c"] += 1; return httpx.Response(404)
    c = PoliteClient(min_interval=0, transport=httpx.MockTransport(h), sleep=lambda s: None)
    with pytest.raises(FetchError) as e:
        c.get_json("https://x.test/a")
    assert n["c"] == 1 and not e.value.retryable


def test_rate_limit_spacing_between_calls_to_same_host():
    sleeps = []
    c = PoliteClient(min_interval=2.0, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})), sleep=sleeps.append)
    c.get_json("https://x.test/a"); c.get_json("https://x.test/b")
    assert any(0 < s <= 2.0 for s in sleeps)


# ------------------------------------------------------------------ AtCoder / DMOJ / CodeChef / CLIST
def test_atcoder_submissions_history_contests_problems():
    http, calls = client()
    ad = A.AtCoderAdapter(http)
    page = ad.fetch_submissions("chokudai")
    assert len(page.items) == 30 and page.checkpoint["last_epoch"] > 0
    assert {s.verdict for s in page.items} <= {"AC", "WA", "TLE", "MLE", "RE", "CE", "OTHER"}
    with pytest.raises(NotSupported, match="robots"):  # rating history is robots-disallowed => must never be fetched
        ad.fetch_rating_history("chokudai")
    assert not any("/history/" in u for u in calls)
    assert len(ad.fetch_contests()) == 6
    probs = ad.fetch_problem_metadata()
    assert probs[0].url.startswith("https://atcoder.jp/contests/") and probs[0].rating is None


def test_atcoder_unknown_user():
    http, _ = client()
    with pytest.raises(FetchError, match="not found"):
        A.AtCoderAdapter(http).validate_profile("nobody")


def test_dmoj_contests_and_problems():
    http, _ = client()
    ad = A.DMOJAdapter(http)
    cs = ad.fetch_contests()
    assert cs and cs[0].url.startswith("https://dmoj.ca/contest/") and cs[0].duration_seconds
    ps = ad.fetch_problem_metadata()
    assert len(ps) == 25 and ps[0].external_id == "aplusb"


def test_codechef_contests_timezone_aware():
    http, _ = client()
    cs = A.CodeChefAdapter(http).fetch_contests()
    assert cs and all(c.start_time.tzinfo for c in cs) and cs[0].duration_seconds % 60 == 0


def test_unsupported_capabilities_raise_not_fake_data():
    ad = A.CodeChefAdapter(client()[0])
    for fn in (lambda: ad.fetch_submissions("x"), lambda: ad.fetch_rating_history("x"), lambda: ad.validate_profile("x")):
        with pytest.raises(NotSupported):
            fn()


def test_clist_requires_user_supplied_key(monkeypatch):
    monkeypatch.delenv("CODEMIND_CLIST_KEY", raising=False)
    with pytest.raises(NotSupported):
        A.ClistAdapter(client()[0]).fetch_contests()


# ------------------------------------------------------------------ manual import
def test_manual_import_valid_and_invalid_rows():
    csv_text = "problem,verdict,submitted_at,language\nhttps://leetcode.com/problems/two-sum/,ac,2025-01-02T10:00:00Z,Python\n,WA,2025-01-02T10:00:00Z,\nx,MAYBE,2025-01-02T10:00:00Z,\ny,AC,2999-01-01T00:00:00Z,\n"
    ok, errs = A.parse_manual_import("leetcode", csv_text, "csv")
    assert len(ok) == 1 and ok[0].provenance == "user_imported" and ok[0].verdict == "AC"
    assert [e["row"] for e in errs] == [2, 3, 4]


def test_manual_import_ids_are_stable_for_dedupe():
    row = '[{"problem":"two-sum","verdict":"AC","submitted_at":"2025-01-02T10:00:00Z"}]'
    a, _ = A.parse_manual_import("leetcode", row, "json")
    b, _ = A.parse_manual_import("leetcode", row, "json")
    assert a[0].external_id == b[0].external_id


# ------------------------------------------------------------------ ingestion
@pytest.fixture()
def uid(client):
    register(client)
    with dbmod.SessionLocal() as db:
        return db.scalar(select(User.id))


def _seed_problems_for_fixture(db):
    refs = {f"{r['problem']['contestId']}{r['problem']['index']}": r["problem"] for r in J("cf_user_status.json")["result"] if "contestId" in r["problem"]}
    for ref, p in refs.items():
        db.add(Problem(platform="codeforces", external_id=ref, name=p["name"], rating=p.get("rating", 1500), tags=p.get("tags", []),
                       url=f"https://codeforces.com/contest/{p['contestId']}/problem/{p['index']}"))
    db.commit()
    return refs


def test_sync_is_idempotent_and_links_problems(uid):
    with dbmod.SessionLocal() as db:
        _seed_problems_for_fixture(db)
        prof = ConnectedProfile(user_id=uid, platform="codeforces", handle="tourist")
        db.add(prof); db.commit()
        ad = A.CodeforcesAdapter(client()[0])
        s1 = ingest.sync_profile(db, prof, ad)
        n1 = db.scalar(select(func.count()).select_from(Submission))
        m1 = {m.topic: round(m.p_known, 9) for m in db.scalars(select(TopicMastery))}
        s2 = ingest.sync_profile(db, prof, ad)
        n2 = db.scalar(select(func.count()).select_from(Submission))
        m2 = {m.topic: round(m.p_known, 9) for m in db.scalars(select(TopicMastery))}
        assert s1["submissions"]["added"] == n1 > 0 and s2["submissions"]["added"] == 0
        assert n1 == n2 and m1 == m2 and m1, "re-sync must not change mastery"
        assert db.scalar(select(func.count()).select_from(Submission).where(Submission.problem_id.is_(None))) == 0
        assert prof.status == "ok" and prof.last_synced_at is not None and prof.data_level == "public_api"
        solved = db.scalars(select(ProblemStatus).where(ProblemStatus.solved.is_(True))).all()
        assert solved and all(p.provenance == "verified_submission" for p in solved)


def test_unlinked_problems_keep_ref_not_dropped(uid):
    with dbmod.SessionLocal() as db:
        prof = ConnectedProfile(user_id=uid, platform="codeforces", handle="tourist")
        db.add(prof); db.commit()
        ingest.sync_profile(db, prof, A.CodeforcesAdapter(client()[0]))
        assert db.scalar(select(func.count()).select_from(Submission).where(Submission.problem_id.is_(None))) > 0
        assert db.scalar(select(func.count()).select_from(Submission).where(Submission.problem_ref == "")) == 0


def test_job_retry_backoff_then_dead_letter(uid):
    with dbmod.SessionLocal() as db:
        prof = ConnectedProfile(user_id=uid, platform="codeforces", handle="tourist")
        db.add(prof); db.commit()
        job = ingest.enqueue(db, "profile_sync", "codeforces", uid, prof.id)
        assert ingest.enqueue(db, "profile_sync", "codeforces", uid, prof.id).id == job.id  # idempotent
        boom = A.CodeforcesAdapter(PoliteClient(min_interval=0, retries=0, transport=httpx.MockTransport(lambda r: httpx.Response(503)), sleep=lambda s: None))
        ingest.run_job(db, job, boom)
        assert job.status == "queued" and job.attempts == 1 and job.run_after > job.created_at
        ingest.run_job(db, job, boom); ingest.run_job(db, job, boom)
        assert job.status == "dead" and job.attempts == 3 and "503" in job.error
        assert prof.status == "error" and prof.last_error


def test_unsupported_job_goes_dead_without_retry(uid):
    with dbmod.SessionLocal() as db:
        job = ingest.enqueue(db, "contests", "leetcode")
        ingest.run_job(db, job)
        assert job.status == "dead" and job.attempts == 1 and "unsupported" in job.error


def test_contest_and_problem_jobs_upsert_idempotently(uid):
    with dbmod.SessionLocal() as db:
        ad = A.DMOJAdapter(client()[0])
        j = ingest.enqueue(db, "contests", "dmoj"); ingest.run_job(db, j, ad)
        first = j.stats["added"]
        j2 = ingest.enqueue(db, "contests", "dmoj"); ingest.run_job(db, j2, ad)
        assert first > 0 and j2.stats["added"] == 0 and j2.stats["updated"] == 0
        assert db.scalar(select(func.count()).select_from(Contest)) == first
