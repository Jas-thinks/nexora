import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.models.user import User
from app.services import codeforces, recommender, sheets
from tests.conftest import auth, register

FX = json.loads((Path(__file__).parent / "fixtures" / "cf_problemset_slice.json").read_text())


@pytest.fixture()
def seeded(client):
    t = register(client)
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User)); u.role = "admin"; db.commit()
        codeforces.upsert_problems(db, codeforces.normalize(FX))
    t = client.post("/auth/login", json={"email": "a@example.com", "password": "correct-horse-battery"}).json()
    return client, auth(t)


def test_normalize_keeps_unrated_as_none_and_builds_ids():
    items = codeforces.normalize(FX)
    by = {i["external_id"]: i for i in items}
    assert by["4A"]["rating"] == 800 and by["4A"]["url"].endswith("/problem/4/A")
    assert any(i["rating"] is None for i in items)  # unrated never guessed


def test_upsert_is_idempotent(client):
    with dbmod.SessionLocal() as db:
        items = codeforces.normalize(FX)
        first = codeforces.upsert_problems(db, items)
        second = codeforces.upsert_problems(db, items)
    assert first["added"] > 0 and second == {"added": 0, "updated": 0, "total": len(items)}


def test_parse_ref_variants():
    assert sheets.parse_ref("4A") == "4A"
    assert sheets.parse_ref("1352/c") == "1352C"
    assert sheets.parse_ref("https://codeforces.com/problemset/problem/4/A") == "4A"
    assert sheets.parse_ref("https://codeforces.com/contest/1352/problem/C") == "1352C"
    assert sheets.parse_ref("garbage!") is None


def test_sheet_import_reports_missing_and_dedupes(seeded):
    c, h = seeded
    r = c.post("/sheets/import", headers=h, json={"slug": "my-sheet", "title": "Mine", "items": [
        {"problem": "4A"}, {"problem": "4/A"}, {"problem": "999999Z"}, {"problem": "nope"}]})
    assert r.status_code == 201 and r.json()["imported"] == 1 and r.json()["missing"] == ["999999Z", "nope"]


def test_starter_sheet_seed_and_progress(seeded):
    c, h = seeded
    assert c.post("/sheets/seed-starter", headers=h).json()["imported"] == 10
    sheet = c.get("/sheets", headers=h).json()[0]
    assert sheet["total"] == 10 and sheet["solved"] == 0
    detail = c.get(f"/sheets/{sheet['id']}", headers=h).json()
    pid = detail["items"][0]["id"]
    c.post("/progress", headers=h, json={"problem_id": pid, "solved": True})
    assert c.get("/sheets", headers=h).json()[0]["solved"] == 1


def test_private_sheet_not_visible_to_others(seeded):
    c, h = seeded
    sid = c.post("/sheets/import", headers=h, json={"slug": "secret", "title": "S", "items": [{"problem": "4A"}]}).json()["sheet_id"]
    other = register(c, "b@example.com")
    assert c.get(f"/sheets/{sid}", headers=auth(other)).status_code == 404
    assert all(s["slug"] != "secret" for s in c.get("/sheets", headers=auth(other)).json())


def test_sheet_import_validation(seeded):
    c, h = seeded
    assert c.post("/sheets/import", headers=h, json={"slug": "Bad Slug", "title": "x", "items": []}).status_code == 422


def test_non_admin_cannot_sync_or_seed(client):
    t = register(client)
    assert client.post("/catalog/sync/codeforces", headers=auth(t)).status_code == 403
    assert client.post("/sheets/seed-starter", headers=auth(t)).status_code == 403


def test_estimate_rating():
    assert recommender.estimate_rating([]) == (800, "none")
    est, conf = recommender.estimate_rating([800] * 3 + [1200, 1300])
    assert est >= 800 and conf == "low"


def test_failure_lowers_mastery_success_raises(seeded):
    c, h = seeded
    probs = c.get("/problems?min_rating=1200", headers=h).json()["items"]
    p = probs[0]
    c.post("/progress", headers=h, json={"problem_id": p["id"], "solved": False})
    m1 = {t["topic"]: t["mastery"] for t in c.get("/mastery", headers=h).json()["topics"]}
    c.post("/progress", headers=h, json={"problem_id": p["id"], "solved": True})
    m2 = {t["topic"]: t["mastery"] for t in c.get("/mastery", headers=h).json()["topics"]}
    assert all(m2[t] > m1[t] for t in m1)


def test_recommendations_are_unsolved_in_window_with_reasons(seeded):
    c, h = seeded
    c.post("/sheets/seed-starter", headers=h)
    easy = c.get("/problems?max_rating=800", headers=h).json()["items"]
    for p in easy[:10]:
        c.post("/progress", headers=h, json={"problem_id": p["id"], "solved": True})
    rec = c.get("/recommendations?count=5", headers=h).json()
    solved_ids = {p["id"] for p in easy[:10]}
    assert 800 <= rec["estimated_rating"] <= 900 and rec["confidence"] == "medium"  # capped at hardest solve + 100
    assert rec["items"], "fixture has 1200+ problems inside the window?"
    for it in rec["items"]:
        assert it["problem_id"] not in solved_ids and rec["window"][0] <= it["rating"] <= rec["window"][1]
        assert it["reasons"]


def test_recommendations_require_auth(client):
    assert client.get("/recommendations").status_code == 401


def test_estimate_is_shrunk_when_evidence_is_thin():
    thin, _ = recommender.estimate_rating([1600, 1600])
    full, _ = recommender.estimate_rating([1600] * 12)
    assert thin < full == 1600
    assert thin == 1000  # 800 + 0.2*(1600-800) = 960 -> rounds to 1000
