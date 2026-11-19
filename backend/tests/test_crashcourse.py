from datetime import date, timedelta

from sqlalchemy import select

from app.core import db as dbmod
from app.models.catalog import Problem, ProblemStatus
from app.models.resources import CrashCourse
from app.resources import company_lists as cl
from tests.conftest import auth, register

TOPICS = [("Array, Hash Table", "Easy"), ("Two Pointers", "Medium"), ("Sliding Window", "Medium"), ("Stack", "Medium"), ("Binary Search", "Medium"), ("Linked List", "Easy"),
          ("Tree, Binary Tree", "Medium"), ("Heap (Priority Queue)", "Hard"), ("Graph Theory, Depth-First Search", "Medium"), ("Backtracking", "Medium"), ("Dynamic Programming", "Hard"),
          ("Greedy", "Medium"), ("Trie", "Medium"), ("Design", "Medium")]


def csv(prefix, k):
    rows = ["Difficulty,Title,Frequency,Acceptance Rate,Link,Topics"]
    for i, (tags, diff) in enumerate(TOPICS):
        for j in range(k):
            rows.append(f'{diff.upper()},{prefix} {i}-{j},{90 - j},0.5,https://leetcode.com/problems/{prefix.lower()}-{i}-{j},"{tags}"')
    return "\n".join(rows)


def load():
    with dbmod.SessionLocal() as db:
        cl.store_company(db, "TCS", cl.parse_csv(csv("A", 6)), set())
        cl.store_company(db, "Infosys", cl.parse_csv(csv("A", 4) + "\n" + csv("B", 2).split("\n", 1)[1]), set())


def mk(client, email="cc@example.com"):
    return auth(register(client, email))


def test_30_day_both_track_structure(client):
    h = mk(client); load()
    r = client.post("/planner/crash-course", headers=h, json={"days": 30, "track": "both", "level": "entry", "target": "service", "hours": 3}).json()
    plan = r["plan"]
    assert len(plan) == 30 and r["days"] == 30
    kinds = lambda d: {t["kind"] for t in plan[d - 1]["tasks"]}
    assert {"review", "mock", "design"} <= kinds(7) and {"review", "mock"} <= kinds(14) and "Final" in plan[29]["theme"]  # a mock/review day every 7th and the last day
    ids = [t["id"] for p in plan for t in p["tasks"]]
    assert len(ids) == len(set(ids))
    problems = [t for p in plan for t in p["tasks"] if t["kind"] == "problem"]
    assert problems and len({t["problem_id"] for t in problems}) == len(problems)  # no problem scheduled twice
    assert all(t["url"].startswith("https://leetcode.com/problems/") for t in problems)
    assert any(t["kind"] == "design" and t.get("question") for p in plan for t in p["tasks"]) and any(t["title"].startswith("System design concept") for p in plan for t in p["tasks"])
    assert all(p["minutes"] == sum(t["est_min"] for t in p["tasks"]) for p in plan)
    assert r["status"] == "running" and r["day_number"] == 1 and "not a prediction" in r["note"]


def test_60_day_is_longer_and_dsa_only_has_no_design_study(client):
    h = mk(client); load()
    r60 = client.post("/planner/crash-course", headers=h, json={"days": 60, "track": "dsa", "level": "mid", "target": "service", "hours": 2}).json()
    assert len(r60["plan"]) == 60 and not any(t["kind"] == "design" and p["day"] not in (7, 14, 21, 28, 35, 42, 49, 56, 60) for p in r60["plan"] for t in p["tasks"])
    assert not any(t["title"].startswith("System design concept") for p in r60["plan"] for t in p["tasks"])
    sd = client.post("/planner/crash-course", headers=h, json={"days": 30, "track": "sd", "level": "senior", "target": "service"}).json()
    assert not any(t["kind"] == "problem" for p in sd["plan"] for t in p["tasks"]) and sd["summary"]["design_tasks"] >= 5


def test_already_solved_problems_are_skipped_and_auto_ticked(client):
    h = mk(client); load()
    with dbmod.SessionLocal() as db:
        from app.models.user import User
        uid = db.scalar(select(User.id))
        first = db.scalar(select(Problem.id).where(Problem.external_id == "a-0-0"))
        db.add(ProblemStatus(user_id=uid, problem_id=first, solved=True)); db.commit()
    r = client.post("/planner/crash-course", headers=h, json={"days": 30, "track": "dsa", "level": "entry", "target": "tcs", "hours": 2}).json()
    assert first not in {t.get("problem_id") for p in r["plan"] for t in p["tasks"]}
    # solve a scheduled problem later: it auto-completes without the student ticking
    t = next(t for p in r["plan"] for t in p["tasks"] if t["kind"] == "problem")
    with dbmod.SessionLocal() as db:
        from app.models.user import User
        db.add(ProblemStatus(user_id=db.scalar(select(User.id)), problem_id=t["problem_id"], solved=True)); db.commit()
    v = client.get("/planner/crash-course", headers=h).json()
    got = next(x for p in v["plan"] for x in p["tasks"] if x["id"] == t["id"])
    assert got["done"] is True and got["auto"] is True


def test_toggle_progress_overdue_and_streak(client):
    h = mk(client); load()
    r = client.post("/planner/crash-course", headers=h, json={"days": 30, "track": "both", "level": "entry", "target": "service"}).json()
    day1 = r["plan"][0]["tasks"]
    for t in day1:
        v = client.post(f"/planner/crash-course/tasks/{t['id']}/toggle", headers=h).json()
    assert v["plan"][0]["complete"] is True and v["progress"]["done"] == len(day1) and v["streak_days"] == 1
    assert client.post(f"/planner/crash-course/tasks/{day1[0]['id']}/toggle", headers=h).json()["plan"][0]["complete"] is False  # toggles back
    assert client.post("/planner/crash-course/tasks/nope/toggle", headers=h).status_code == 404
    with dbmod.SessionLocal() as db:  # pretend the course started 3 days ago
        c = db.scalar(select(CrashCourse)); c.started_on = (date.today() - timedelta(days=3)).isoformat(); db.commit()
    v = client.get("/planner/crash-course", headers=h).json()
    assert v["day_number"] == 4 and v["overdue_count"] > 0 and all(o["day"] < 4 for o in v["overdue"])


def test_new_course_replaces_old_and_validation(client):
    h = mk(client); load()
    a = client.post("/planner/crash-course", headers=h, json={"days": 30, "target": "service"}).json()["id"]
    b = client.post("/planner/crash-course", headers=h, json={"days": 60, "target": "service"}).json()["id"]
    assert a != b and client.get("/planner/crash-course", headers=h).json()["id"] == b
    assert client.post("/planner/crash-course", headers=h, json={"days": 45}).status_code == 422
    assert client.post("/planner/crash-course", headers=h, json={"days": 30, "target": "no-such-company"}).status_code == 422
    assert client.post("/planner/crash-course", headers=h, json={"days": 30, "hours": 20}).status_code == 422
    assert client.delete("/planner/crash-course", headers=h).status_code == 204 and client.get("/planner/crash-course", headers=h).json()["id"] is None


def test_without_company_data_dsa_track_says_so_but_sd_still_works(client):
    h = mk(client)
    assert "company-list ingest" in client.post("/planner/crash-course", headers=h, json={"days": 30, "track": "dsa", "target": "service"}).json()["detail"]
    assert client.post("/planner/crash-course", headers=h, json={"days": 30, "track": "sd", "target": "service"}).status_code == 201


def test_courses_are_private(client):
    h1 = mk(client, "p1@example.com"); load()
    tid = client.post("/planner/crash-course", headers=h1, json={"days": 30, "target": "service"}).json()["plan"][0]["tasks"][0]["id"]
    h2 = mk(client, "p2@example.com")
    assert client.get("/planner/crash-course", headers=h2).json()["id"] is None and client.post(f"/planner/crash-course/tasks/{tid}/toggle", headers=h2).status_code == 404
