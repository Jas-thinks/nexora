import pytest

from app.core import db as dbmod
from app.integrations import adapters as A
from app.models.catalog import Problem
from app.services import sheet_import
from tests.conftest import auth, register
from tests.test_integrations import client as http_client


@pytest.fixture()
def two(client):
    a, b = register(client, "a@example.com"), register(client, "b@example.com")
    return client, auth(a), auth(b)


def test_platform_matrix_endpoint_is_public_facing_and_honest(two):
    c, h, _ = two
    d = c.get("/platforms").json()
    lc = next(p for p in d["platforms"] if p["slug"] == "leetcode")
    assert lc["status"] == "manual_import" and not lc["has_adapter"]
    assert "ESTIMATED" in d["data_levels"] and d["discovery_leads_not_yet_crawled"]


def test_sheet_sources_report_unavailable_ones_truthfully(two):
    c, *_ = two
    src = {s["id"]: s for s in c.get("/sheet-sources").json()}
    assert src["cp31"]["status"] == "not_importable" and src["striver-cp"]["status"] == "unavailable"
    assert src["striver-sde"]["status"] == "importable" and "DIFFERENT" in src["striver-sde"]["note"]


def test_link_only_platform_is_labelled_link_only_and_cannot_sync(two):
    c, h, _ = two
    r = c.post("/profiles", headers=h, json={"platform": "leetcode", "handle": "me"})
    assert r.status_code == 201 and r.json()["data_level"] == "link_only"
    assert c.post(f"/profiles/{r.json()['id']}/sync", headers=h).status_code == 422


def test_link_validates_handle_against_real_platform(two, monkeypatch):
    c, h, _ = two
    monkeypatch.setitem(A.ADAPTERS, "codeforces", lambda: A.CodeforcesAdapter(http_client({"/api/user.info": ({"status": "FAILED", "comment": "handles: User with handle zzz not found"}, 400)})[0]))
    assert c.post("/profiles", headers=h, json={"platform": "codeforces", "handle": "zzz"}).status_code == 422
    monkeypatch.setitem(A.ADAPTERS, "codeforces", lambda: A.CodeforcesAdapter(http_client()[0]))
    r = c.post("/profiles", headers=h, json={"platform": "codeforces", "handle": "tourist"})
    assert r.status_code == 201 and r.json()["data_level"] == "public_api"
    assert c.post("/profiles", headers=h, json={"platform": "codeforces", "handle": "tourist"}).status_code == 409


def test_rejects_unknown_platform_and_bad_handle(two):
    c, h, _ = two
    assert c.post("/profiles", headers=h, json={"platform": "nope", "handle": "x"}).status_code == 404
    assert c.post("/profiles", headers=h, json={"platform": "leetcode", "handle": "../../etc"}).status_code == 422


def test_users_cannot_see_or_touch_each_others_profiles(two):
    c, ha, hb = two
    pid = c.post("/profiles", headers=ha, json={"platform": "leetcode", "handle": "alice"}).json()["id"]
    assert c.get("/profiles", headers=hb).json() == []
    assert c.delete(f"/profiles/{pid}", headers=hb).status_code == 404
    assert c.post(f"/profiles/{pid}/sync", headers=hb).status_code == 404
    assert c.post(f"/profiles/{pid}/import", headers=hb, files={"file": ("x.csv", b"a")}).status_code == 404


def test_manual_import_upload_labels_data_and_reports_rejects(two):
    c, h, _ = two
    with dbmod.SessionLocal() as db:
        sheet_import.import_sheet_spec(db, {"slug": "s", "title": "s", "source_url": "x", "sections": [{"name": "A", "items": [{"url": "https://leetcode.com/problems/two-sum/", "title": "Two Sum"}]}]})
    pid = c.post("/profiles", headers=h, json={"platform": "leetcode", "handle": "me"}).json()["id"]
    csv = b"problem,verdict,submitted_at,language\nhttps://leetcode.com/problems/two-sum/,AC,2025-01-02T10:00:00Z,Python\nbad,NOPE,2025-01-02T10:00:00Z,\nhttps://codeforces.com/contest/4/problem/A,AC,2025-01-02T10:00:00Z,C++\n"
    r = c.post(f"/profiles/{pid}/import", headers=h, files={"file": ("subs.csv", csv)})
    assert r.status_code == 200 and r.json()["added"] == 1 and r.json()["rejected_count"] == 2 and "USER_IMPORTED" in r.json()["label"]
    again = c.post(f"/profiles/{pid}/import", headers=h, files={"file": ("subs.csv", csv)}).json()
    assert again["added"] == 0 and again["duplicates"] == 1
    assert c.get("/profiles", headers=h).json()[0]["data_level"] == "user_imported"
    ex = c.get("/explorer?solved=true", headers=h).json()
    assert ex["total"] == 1  # imported AC counts as solved, provenance user_import


def test_manual_import_rejects_garbage_and_oversize(two):
    c, h, _ = two
    pid = c.post("/profiles", headers=h, json={"platform": "leetcode", "handle": "me"}).json()["id"]
    assert c.post(f"/profiles/{pid}/import", headers=h, files={"file": ("x.json", b"{not json")}).status_code == 422
    assert c.post(f"/profiles/{pid}/import", headers=h, files={"file": ("x.csv", b"x" * 2_000_100)}).status_code == 413


def test_explorer_filters(two):
    c, h, _ = two
    with dbmod.SessionLocal() as db:
        db.add_all([Problem(platform="codeforces", external_id="1A", name="Easy", rating=800, tags=["math"], url="u1", canonical_url="u1"),
                    Problem(platform="codeforces", external_id="2B", name="Hard", rating=2000, tags=["dp", "math"], url="u2", canonical_url="u2"),
                    Problem(platform="leetcode", external_id="two-sum", name="Two Sum", rating=None, tags=[], url="u3", canonical_url="u3", source_difficulty="Easy")])
        db.commit()
    g = lambda q: c.get("/explorer?" + q, headers=h).json()
    assert g("platform=leetcode")["total"] == 1 and g("difficulty=easy")["items"][0]["name"] == "Two Sum"
    assert [p["name"] for p in g("min_rating=1000")["items"]] == ["Hard"] and g("tag=dp")["total"] == 1
    assert g("")["platform_counts"] == {"codeforces": 2, "leetcode": 1}
    assert g("solved=false")["total"] == 3
    assert c.get("/explorer").status_code == 401


def test_admin_endpoints_forbidden_to_students(two):
    c, h, _ = two
    for path in ("/admin/jobs/run", "/admin/sheets/import/neetcode", "/admin/sync/contests/dmoj"):
        assert c.post(path, headers=h).status_code == 403


def test_contests_empty_state_is_explicit(two):
    c, h, _ = two
    d = c.get("/contests", headers=h).json()
    assert d["items"] == [] and "not synced" in d["note"]


def test_background_worker_drains_queue_without_admin_action(client, monkeypatch):
    """The app's worker thread must pick up queued jobs on its own (UI 'Sync now' relies on this)."""
    import time
    from app.core.config import get_settings
    from app.integrations import adapters as A2
    from app.main import create_app
    from app.models.integrations import SyncJob
    from app.services import ingest
    from tests.test_integrations import client as http_client
    monkeypatch.setenv("CODEMIND_WORKER_ENABLED", "true"); monkeypatch.setenv("CODEMIND_WORKER_POLL_SECONDS", "0.1")
    get_settings.cache_clear()
    monkeypatch.setitem(A2.ADAPTERS, "dmoj", lambda: A2.DMOJAdapter(http_client()[0]))
    try:
        from fastapi.testclient import TestClient
        with TestClient(create_app()):  # entering the context runs lifespan => starts the worker
            with dbmod.SessionLocal() as db:
                job_id = ingest.enqueue(db, "contests", "dmoj").id
            for _ in range(60):
                time.sleep(0.1)
                with dbmod.SessionLocal() as db:
                    if db.get(SyncJob, job_id).status == "succeeded":
                        break
            with dbmod.SessionLocal() as db:
                assert db.get(SyncJob, job_id).status == "succeeded"
    finally:
        get_settings.cache_clear()
