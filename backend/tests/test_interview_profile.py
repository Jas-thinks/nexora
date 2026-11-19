import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.mentor import get_router
from app.core import db as dbmod
from app.llm.router import Router
from app.models.ai import CodeRun, InterviewSession
from app.models.catalog import Problem, Sheet, SheetItem
from app.models.user import User
from app.services import interview as I
from tests.conftest import auth, register
from tests.test_mentor import Fake

NOW = datetime.now(UTC)


@pytest.fixture()
def env(client):
    t = register(client); h = auth(t)
    with dbmod.SessionLocal() as db:
        sh = Sheet(slug="s", title="s", owner_id=None); db.add(sh); db.flush()
        for i, (n, d) in enumerate((("Two Sum", "Easy"), ("LRU Cache", "Medium"), ("Merge Intervals", "Medium"))):
            p = Problem(platform="leetcode", external_id=f"p{i}", name=n, rating=None, tags=[], url=f"https://leetcode.com/problems/p{i}/", canonical_url=f"https://leetcode.com/problems/p{i}/", source_difficulty=d); db.add(p); db.flush()
            db.add(SheetItem(sheet_id=sh.id, problem_id=p.id, section="Arrays & Hashing", position=i))
        db.commit()
        uid = db.scalar(select(User.id))
    return client, h, uid


def test_rubric_parsing_is_strict():
    ok = I.parse_rubric('x {"approach":4,"communication":3,"complexity":5,"edge_cases":2,"summary":"good","improvements":["a","b"]} y')
    assert ok["scores"] == {"approach": 4, "communication": 3, "complexity": 5, "edge_cases": 2} and ok["improvements"] == ["a", "b"]
    assert I.parse_rubric("nope") is None and I.parse_rubric('{"approach":9,"communication":3,"complexity":5,"edge_cases":2}') is None
    assert I.parse_rubric('{"approach":4}') is None and I.parse_rubric('{"approach":"x","communication":3,"complexity":5,"edge_cases":2}') is None


def test_start_validates_picks_a_sheet_problem_and_hides_nothing_it_should_not_store(env):
    c, h, uid = env
    assert c.post("/interview", headers=h, json={"minutes": 7}).status_code == 422
    d = c.post("/interview", headers=h, json={"minutes": 30}).json()
    assert d["status"] == "running" and d["problem"]["platform"] == "leetcode" and d["seconds_left"] > 1700 and "statement" in d["problem"]["note"].lower() or "no statement" in d["problem"]["note"].lower()
    assert d["transcript"] == []


def test_offline_interviewer_asks_scripted_questions_in_order_and_never_gives_a_solution(env):
    c, h, uid = env
    c.app.dependency_overrides[get_router] = lambda: Router({}, [])
    sid = c.post("/interview", headers=h, json={"minutes": 30}).json()["id"]
    qs = [c.post(f"/interview/{sid}/say", headers=h, json={"message": "I would sort first"}).json() for _ in range(3)]
    assert all(q["offline"] for q in qs) and "approach" in qs[0]["answer"].lower() and "complexity" in qs[1]["answer"].lower() and "edge cases" in qs[2]["answer"].lower()
    assert [m["role"] for m in c.get(f"/interview/{sid}", headers=h).json()["transcript"]] == ["user", "assistant"] * 3


def test_llm_prompt_has_interviewer_rules_and_problem_metadata_only(env):
    c, h, uid = env
    f = Fake(reply="What is the complexity?")
    c.app.dependency_overrides[get_router] = lambda: Router({"f": f}, ["f"])
    sid = c.post("/interview", headers=h, json={"minutes": 30}).json()["id"]
    c.post(f"/interview/{sid}/say", headers=h, json={"message": "Use a hash map"})
    sysmsg, user = f.calls[0][0]["content"], f.calls[0][-1]["content"]
    assert "INTERVIEW MODE" in sysmsg and "Never reveal the solution" in sysmsg and "<problem name=" in user and "statement is not stored" in user


def test_finish_scores_with_llm_labels_it_an_estimate_and_records_measured_facts(env):
    c, h, uid = env
    rubric = '{"approach":4,"communication":3,"complexity":4,"edge_cases":2,"summary":"ok","improvements":["state edge cases earlier"]}'
    f = Fake(reply="Q?"); f2 = Fake(reply=rubric)
    class Seq(Fake):
        def __init__(self): super().__init__("seq"); self.n = 0
        def chat(self, messages, *a, **k):
            self.n += 1
            return super().chat(messages, *a, **k).__class__(rubric if "Score this mock" in messages[0]["content"] else "Next question?", "seq", "m", 1, 1, 1)
    c.app.dependency_overrides[get_router] = lambda: Router({"seq": Seq()}, ["seq"])
    sid = c.post("/interview", headers=h, json={"minutes": 30}).json()["id"]
    for t in ("hash map", "O(n)"): c.post(f"/interview/{sid}/say", headers=h, json={"message": t})
    with dbmod.SessionLocal() as db:
        pid = db.get(InterviewSession, sid).problem_id
        db.add(CodeRun(user_id=uid, problem_id=pid, language="python", code="x", verdict="WA", created_at=datetime.now(UTC) + timedelta(seconds=1)))
        db.add(CodeRun(user_id=uid, problem_id=pid, language="python", code="x", verdict="OK", created_at=datetime.now(UTC) + timedelta(seconds=2))); db.commit()
    r = c.post(f"/interview/{sid}/finish", headers=h, json={"self_eval": {"approach": 3, "complexity": 9}}).json()
    assert r["status"] == "finished" and r["rubric"]["scored"]["scores"]["approach"] == 4 and "NOT verified" in r["rubric"]["scored"]["source"]
    assert r["rubric"]["measured"]["candidate_turns"] == 2 and r["rubric"]["measured"]["code_runs"] == 2 and r["self_eval"] == {"approach": 3}  # invalid self-eval value dropped
    assert c.post(f"/interview/{sid}/say", headers=h, json={"message": "more"}).status_code == 409
    assert c.get("/interview", headers=h).json()[0]["scores"]["edge_cases"] == 2


def test_finish_without_llm_or_conversation_never_invents_a_score(env):
    c, h, uid = env
    c.app.dependency_overrides[get_router] = lambda: Router({}, [])
    s1 = c.post("/interview", headers=h, json={"minutes": 30}).json()["id"]
    r = c.post(f"/interview/{s1}/finish", headers=h, json={}).json()
    assert r["rubric"]["scored"] is None and "Not enough conversation" in r["rubric"]["message"]
    s2 = c.post("/interview", headers=h, json={"minutes": 30}).json()["id"]
    for _ in range(2): c.post(f"/interview/{s2}/say", headers=h, json={"message": "ok"})
    assert "No LLM available" in c.post(f"/interview/{s2}/finish", headers=h, json={}).json()["rubric"]["message"]


def test_interviews_are_private_to_their_owner(env):
    c, h, uid = env
    sid = c.post("/interview", headers=h, json={"minutes": 30}).json()["id"]
    other = auth(register(c, "b@example.com"))
    assert c.get(f"/interview/{sid}", headers=other).status_code == 404 and c.post(f"/interview/{sid}/say", headers=other, json={"message": "x"}).status_code == 404
    assert c.post(f"/interview/{sid}/finish", headers=other, json={}).status_code == 404 and c.get("/interview", headers=other).json() == []


def test_public_profile_requires_explicit_sharing_and_hides_private_users_identically(env):
    c, h, uid = env
    assert c.get(f"/profile/{uid}").status_code == 404 and c.get("/profile/99999").status_code == 404  # private == missing
    c.put("/me/prefs", headers=h, json={"share_progress": True})
    d = c.get(f"/profile/{uid}").json()   # no auth header
    assert d["name"] == "A" and d["level"] >= 1 and "email" not in json.dumps(d) and d["badges"] == [] and "ratings" in d
    c.put("/me/prefs", headers=h, json={"share_progress": False})
    assert c.get(f"/profile/{uid}").status_code == 404
