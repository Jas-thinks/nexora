import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.core import db as dbmod
from app.integrations.http import PoliteClient
from app.models.catalog import Problem, ProblemStatisticsSnapshot, SyncCheckpoint, SyncFailure
from app.services import ingest
from app.sources import sources as S
from app.sources.backfill import run_backfill, run_details

FX = Path(__file__).parent / "fixtures"
J = lambda n: json.loads((FX / n).read_text())


def http(routes, calls=None):
    def h(req: httpx.Request):
        if calls is not None:
            calls.append(str(req.url))
        for key, (body, code) in routes.items():
            if key in str(req.url):
                return httpx.Response(code, json=body) if not isinstance(body, str) else httpx.Response(code, text=body)
        return httpx.Response(404, json={})
    return PoliteClient(min_interval=0, retries=1, transport=httpx.MockTransport(h), sleep=lambda s: None)


def cc_http(fail_page=None):
    def h(req: httpx.Request):
        pg = int(req.url.params.get("page", "1"))
        if fail_page and pg == fail_page:
            return httpx.Response(503)
        return httpx.Response(200, json=J(f"cc_p{pg}.json") if pg <= 3 else {"status": "success", "data": [], "count": "21697"})
    return PoliteClient(min_interval=0, retries=0, transport=httpx.MockTransport(h), sleep=lambda s: None)


def cc_source(client):
    s = S.CodeChefSource(client); s.PAGE = 3; return s


@pytest.fixture()
def db(client):
    with dbmod.SessionLocal() as s:
        yield s


# ---------------------------------------------------------------- parsers on real responses
def test_codeforces_source_carries_contest_difficulty_and_statistics():
    src = S.CodeforcesSource(http({"problemset.problems": ({"status": "OK", "result": J("cf_stats_slice.json")["result"]}, 200)}))
    (recs, nxt), = list(src.pages(None))
    assert nxt is None and recs
    rated = next(r for r in recs if r.rating)
    assert rated.contest_ref and rated.problem_index and rated.solved_count and rated.raw["stat"]["solvedCount"] == rated.solved_count
    assert any(r.rating is None for r in recs)  # unrated stays None


def test_atcoder_source_uses_merged_json_with_solver_counts():
    src = S.AtCoderSource(http({"merged-problems": (J("ac_merged_slice.json"), 200), "problem-models": ({}, 200)}))
    (recs, _), = list(src.pages(None))
    assert len(recs) == 12 and recs[0].solved_count == recs[0].raw["solver_count"] and recs[0].url.startswith("https://atcoder.jp/contests/")


def test_yukicoder_euler_cses_parsers():
    (y, _), = list(S.YukicoderSource(http({"api/v1/problems": (J("yuki_slice.json"), 200)})).pages(None))
    assert len(y) == 28 and y[0].url == "https://yukicoder.me/problems/no/1" and y[0].published_at.tzinfo
    e = S.ProjectEulerSource.parse((FX / "euler_min.txt").read_text())
    assert e[0].external_id == "1" and e[0].solved_count > 100000 and e[0].url.endswith("problem=1")
    c = S.CSESSource.parse((FX / "cses_slice.html").read_text())
    assert c[0].external_id == "1068" and c[0].solved_count < c[0].submission_count and c[0].tags == ["Introductory Problems"]
    assert len({r.external_id for r in c}) == len(c)  # no duplicates


def test_dmoj_pagination_and_details():
    pages = []
    def h(req):
        pg = int(req.url.params.get("page", "1")); pages.append(pg)
        return httpx.Response(200, json={"data": {"objects": [{"code": f"p{pg}", "name": f"P{pg}", "types": ["dp"], "group": "G", "points": 5.0}], "has_more": pg < 3}})
    src = S.DMOJSource(PoliteClient(min_interval=0, transport=httpx.MockTransport(h), sleep=lambda s: None))
    got = [(len(r), n) for r, n in src.pages(None)]
    assert got == [(1, {"page": 2}), (1, {"page": 3}), (1, None)] and pages == [1, 2, 3]
    d = S.DMOJSource(http({"problem/aplusb": (J("dmoj_detail.json"), 200)})).details("aplusb")
    assert d.time_limit_ms == 5000 and d.memory_limit_kb == 262144


# ---------------------------------------------------------------- backfill engine
def test_backfill_is_idempotent_and_refresh_pass_changes_nothing(db):
    r1 = run_backfill(db, cc_source(cc_http()))
    assert r1["status"] == "complete" and r1["added"] == 9 and r1["discovered"] == 21697
    r2 = run_backfill(db, cc_source(cc_http()))  # second full pass = refresh
    assert r2["added"] == 0 and r2["updated"] == 0 and r2["unchanged"] == 9 and r2["snapshots"] == 0
    assert db.scalar(select(func.count()).select_from(Problem)) == 9
    p = db.scalar(select(Problem))
    assert p.source and p.observed_at and p.source_record and p.canonical_url and p.statement_access == "link_only"


def test_interrupt_then_resume_from_checkpoint_without_restarting(db):
    a = run_backfill(db, cc_source(cc_http()), max_pages=1)
    assert a["status"] == "partial" and a["retrieved"] == 3
    cp = db.scalar(select(SyncCheckpoint))
    assert cp.cursor == {"page": 2} and not cp.done
    calls = []
    def h(req):
        calls.append(int(req.url.params.get("page", "1")))
        pg = calls[-1]
        return httpx.Response(200, json=J(f"cc_p{pg}.json") if pg <= 3 else {"status": "success", "data": [], "count": "21697"})
    b = run_backfill(db, cc_source(PoliteClient(min_interval=0, transport=httpx.MockTransport(h), sleep=lambda s: None)))
    assert b["status"] == "complete" and calls[0] == 2, "must resume at page 2, not page 1"
    assert db.scalar(select(func.count()).select_from(Problem)) == 9 and db.scalar(select(SyncCheckpoint.done))


def test_failure_mid_run_keeps_progress_records_failure_and_resumes(db):
    r = run_backfill(db, cc_source(cc_http(fail_page=3)))
    assert r["status"] == "interrupted" and r["retrieved"] == 6 and "503" in r["error"]
    f = db.scalar(select(SyncFailure))
    assert f.stage == "enumerate" and "page" in f.ref and not f.resolved
    assert db.scalar(select(SyncCheckpoint.cursor)) == {"page": 3}
    ok = run_backfill(db, cc_source(cc_http()))
    assert ok["status"] == "complete" and db.scalar(select(func.count()).select_from(Problem)) == 9


def test_statistics_snapshots_only_when_counts_change(db):
    run_backfill(db, cc_source(cc_http()))
    n1 = db.scalar(select(func.count()).select_from(ProblemStatisticsSnapshot))
    assert n1 == 9
    changed = J("cc_p1.json"); changed["data"][0]["distinct_successful_submissions"] = "99999"
    def h(req):
        pg = int(req.url.params.get("page", "1"))
        return httpx.Response(200, json=changed if pg == 1 else J(f"cc_p{pg}.json") if pg <= 3 else {"status": "success", "data": [], "count": "21697"})
    r = run_backfill(db, cc_source(PoliteClient(min_interval=0, transport=httpx.MockTransport(h), sleep=lambda s: None)))
    assert r["snapshots"] == 1 and db.scalar(select(func.count()).select_from(ProblemStatisticsSnapshot)) == 10
    assert db.scalar(select(Problem.solved_count).where(Problem.external_id == changed["data"][0]["code"].upper())) == 99999


def test_reconciliation_marks_missing_upstream_and_restores_when_it_returns(db):
    run_backfill(db, cc_source(cc_http()))
    gone = J("cc_p3.json"); gone["data"] = gone["data"][:2]; gone_code = J("cc_p3.json")["data"][2]["code"].upper()
    def h(req):
        pg = int(req.url.params.get("page", "1"))
        return httpx.Response(200, json=gone if pg == 3 else J(f"cc_p{pg}.json") if pg < 3 else {"status": "success", "data": [], "count": "21697"})
    r = run_backfill(db, cc_source(PoliteClient(min_interval=0, transport=httpx.MockTransport(h), sleep=lambda s: None)))
    assert r["missing_upstream_marked"] == 1
    assert db.scalar(select(Problem.status).where(Problem.external_id == gone_code)) == "missing_upstream"
    run_backfill(db, cc_source(cc_http()))
    assert db.scalar(select(Problem.status).where(Problem.external_id == gone_code)) == "active"


def test_single_pass_sources_that_are_not_complete_enumerations_are_never_reconciled(db):
    class Partial(S.CodeChefSource):
        complete_enumeration = False
    run_backfill(db, cc_source(cc_http()))
    s = Partial(cc_http()); s.PAGE = 3
    run_backfill(db, s, max_pages=1)  # partial pass cannot declare others missing
    assert db.scalar(select(func.count()).select_from(Problem).where(Problem.status == "missing_upstream")) == 0


def test_details_stage_fills_limits_isolates_failures_and_never_gets_erased(db):
    def lst(req):
        return httpx.Response(200, json={"data": {"objects": [{"code": c, "name": c, "types": [], "points": 1.0} for c in ("aplusb", "ghost")], "has_more": False}})
    def h(req):
        if "/problem/aplusb" in str(req.url):
            return httpx.Response(200, json=J("dmoj_detail.json"))
        if "/problem/ghost" in str(req.url):
            return httpx.Response(404, json={})
        return lst(req)
    client = PoliteClient(min_interval=0, retries=0, transport=httpx.MockTransport(h), sleep=lambda s: None)
    src = S.DMOJSource(client)
    run_backfill(db, src)
    d = run_details(db, src)
    assert d == {"platform": "dmoj", "attempted": 2, "fetched": 1, "failed": 1}
    ap = db.scalar(select(Problem).where(Problem.external_id == "aplusb"))
    assert ap.time_limit_ms == 5000 and db.scalar(select(Problem.status).where(Problem.external_id == "ghost")) == "inaccessible"
    run_backfill(db, src)  # refresh enumeration must not wipe the richer fields
    assert db.scalar(select(Problem.time_limit_ms).where(Problem.external_id == "aplusb")) == 5000
    assert db.scalar(select(func.count()).select_from(SyncFailure).where(SyncFailure.stage == "details")) == 1


def test_backfill_job_kind_runs_through_the_queue_and_retries_interruptions(db, monkeypatch):
    monkeypatch.setitem(S.SOURCES, "codechef", lambda: cc_source(cc_http(fail_page=2)))
    job = ingest.enqueue(db, "backfill", "codechef")
    ingest.run_job(db, job)
    assert job.status == "queued" and job.attempts == 1 and "503" in job.error  # retryable => backoff, checkpoint kept
    monkeypatch.setitem(S.SOURCES, "codechef", lambda: cc_source(cc_http()))
    job.run_after = job.created_at
    ingest.run_job(db, job)
    assert job.status == "succeeded" and db.scalar(select(func.count()).select_from(Problem)) == 9


def test_non_utc_source_timestamps_are_stored_in_utc_and_refresh_is_idempotent(db):
    """Regression: yukicoder publishes JST (+09:00); SQLite drops offsets, which made every refresh report all rows 'updated'."""
    def h(req):
        return httpx.Response(200, json=J("yuki_slice.json"))
    mk = lambda: S.YukicoderSource(PoliteClient(min_interval=0, transport=httpx.MockTransport(h), sleep=lambda s: None))
    run_backfill(db, mk())
    raw = J("yuki_slice.json")[0]["Date"]  # e.g. 2014-07-23T00:20:00+09:00
    stored = db.scalar(select(Problem.published_at).where(Problem.external_id == "1"))
    assert stored.replace(tzinfo=None).isoformat() == "2014-07-22T15:20:00", (raw, stored)  # JST 00:20 == 15:20 UTC previous day
    r = run_backfill(db, mk())
    assert r["updated"] == 0 and r["unchanged"] == 28
