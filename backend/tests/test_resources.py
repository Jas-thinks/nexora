from app.core import db as dbmod
from app.models.catalog import ProblemStatus
from app.resources import company_lists as cl
from app.resources import design_questions as dq
from sqlalchemy import select
from app.models.catalog import Problem

CSV = """Difficulty,Title,Frequency,Acceptance Rate,Link,Topics
EASY,Two Sum,100.0,0.58,https://leetcode.com/problems/two-sum,"Array, Hash Table"
MEDIUM,LRU Cache,80,0.4,https://leetcode.com/problems/lru-cache,"Hash Table, Design"
HARD,Trapping Rain Water,60,0.6,https://leetcode.com/problems/trapping-rain-water,"Array, Two Pointers"
"""
CSV2 = "Difficulty,Title,Frequency,Acceptance Rate,Link,Topics\nEASY,Two Sum,90,0.5,https://leetcode.com/problems/two-sum,Array\nMEDIUM,Group Anagrams,40,0.5,https://leetcode.com/problems/group-anagrams,\"Hash Table, String\"\n"


def reg(client, email="r@example.com"):
    t = client.post("/auth/register", json={"email": email, "display_name": "r", "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def load():
    with dbmod.SessionLocal() as db:
        cl.store_company(db, "TCS", cl.parse_csv(CSV), {"two-sum"})
        cl.store_company(db, "Infosys", cl.parse_csv(CSV2), set())
        cl.store_company(db, "Google", cl.parse_csv(CSV), set())


def test_question_library_is_consistent():
    slugs = [q[0] for q in dq.Q]
    assert len(slugs) == len(set(slugs)) and len(slugs) >= 60
    assert all(q[2] in ("entry", "mid", "senior") and q[4] in ("hld", "lld") and len(q[7]) > 40 for q in dq.Q)


def test_overview_and_tiers(client):
    h = reg(client); load()
    o = client.get("/resources/overview", headers=h).json()
    by = {t["id"]: t for t in o["tiers"]}
    assert by["service"]["companies"] == 2 and by["faang"]["companies"] == 1 and o["distinct_problems"] == 4 and "not official" in o["attribution"]["disclaimer"]
    assert client.get("/resources/overview").status_code in (401, 403)


def test_company_list_filters_progress_and_pagination(client):
    h = reg(client); load()
    items = client.get("/resources/companies?tier=service", headers=h).json()["items"]
    assert {c["slug"] for c in items} == {"tcs", "infosys"}
    assert client.get("/resources/companies?q=goo", headers=h).json()["total"] == 1
    with dbmod.SessionLocal() as db:
        pid = db.scalar(select(Problem.id).where(Problem.external_id == "two-sum"))
        from app.models.user import User
        uid = db.scalar(select(User.id)); db.add(ProblemStatus(user_id=uid, problem_id=pid, solved=True)); db.commit()
    c = client.get("/resources/companies/tcs", headers=h).json()
    assert c["difficulty"]["Easy"] == {"total": 1, "solved": 1} and c["difficulty"]["Hard"]["solved"] == 0 and c["recent_problems"] == 1
    r = client.get("/resources/companies/tcs/problems?sort=frequency", headers=h).json()
    assert [p["name"] for p in r["items"]] == ["Two Sum", "LRU Cache", "Trapping Rain Water"] and r["items"][0]["solved"] is True
    assert client.get("/resources/companies/tcs/problems?unsolved=true", headers=h).json()["total"] == 2
    assert [p["name"] for p in client.get("/resources/companies/tcs/problems?difficulty=Hard", headers=h).json()["items"]] == ["Trapping Rain Water"]
    assert client.get("/resources/companies/tcs/problems?recent=true", headers=h).json()["total"] == 1
    assert [p["name"] for p in client.get("/resources/companies/tcs/problems?topic=design", headers=h).json()["items"]] == ["LRU Cache"]
    assert len(client.get("/resources/companies/tcs/problems?limit=1&offset=1", headers=h).json()["items"]) == 1
    assert client.get("/resources/companies/nope", headers=h).status_code == 404


def test_must_do_ranks_by_how_many_companies_ask(client):
    h = reg(client); load()
    r = client.get("/resources/must-do?tier=service", headers=h).json()["items"]
    assert r[0]["name"] == "Two Sum" and r[0]["companies"] == 2  # asked by both service companies
    assert client.get("/resources/must-do?tier=bogus", headers=h).status_code == 422


def test_system_design_library_filters_and_status(client):
    h = reg(client)
    all_ = client.get("/resources/system-design", headers=h).json()
    assert all_["total"] >= 60 and "not available as open data" in all_["note"]
    entry = client.get("/resources/system-design?level=entry&kind=hld", headers=h).json()["items"]
    assert entry and all(x["level"] == "entry" and x["kind"] == "hld" for x in entry)
    assert [x["slug"] for x in client.get("/resources/system-design?q=snowflake", headers=h).json()["items"]] == ["unique-id-generator"]
    assert client.get("/resources/system-design?kind=lld", headers=h).json()["total"] == 10
