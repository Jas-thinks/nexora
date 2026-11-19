import httpx
from sqlalchemy import func, select

from app.core import db as dbmod
from app.models.catalog import Problem
from app.models.resources import Company, CompanyProblem
from app.resources import company_lists as cl
from app.resources.tiers import tier_of

ALL = """Difficulty,Title,Frequency,Acceptance Rate,Link,Topics
EASY,Two Sum,100.0,0.58,https://leetcode.com/problems/two-sum,"Array, Hash Table"
HARD,Trapping Rain Water,87.9,0.68,https://leetcode.com/problems/trapping-rain-water/,"Array, Two Pointers"
MEDIUM,Weird,5,0.1,https://example.com/not-leetcode,"X"
MEDIUM,,5,0.1,https://leetcode.com/problems/no-title,""
MEDIUM,Bad Freq,abc,0.1,https://leetcode.com/problems/bad-freq,"Stack"
"""
RECENT = "Difficulty,Title,Frequency,Acceptance Rate,Link,Topics\nEASY,Two Sum,100,0.5,https://leetcode.com/problems/two-sum,Array\n"


def test_parse_drops_unrecognised_rows_and_clamps():
    rows = cl.parse_csv(ALL)
    assert [r["slug"] for r in rows] == ["two-sum", "trapping-rain-water", "bad-freq"]
    assert rows[0]["difficulty"] == "Easy" and rows[0]["topics"] == ["Array", "Hash Table"] and rows[2]["frequency"] == 0.0


def test_tiers_are_editorial_and_case_insensitive():
    assert tier_of("Google") == "faang" and tier_of("TCS") == "service" and tier_of("Infosys") == "service" and tier_of("Razorpay") == "product" and tier_of("Nobody Inc") == "other"


def test_store_is_idempotent_and_marks_recent(client):
    with dbmod.SessionLocal() as db:
        rows = cl.parse_csv(ALL)
        r1 = cl.store_company(db, "Acme Corp", rows, {"two-sum"})
        r2 = cl.store_company(db, "Acme Corp", rows, {"two-sum"})
        assert r1["problems"] == 3 and r2["new_problems"] == 0
        co = db.scalar(select(Company).where(Company.slug == "acme-corp"))
        assert co.problem_count == 3 and co.source == cl.SOURCE
        assert db.scalar(select(func.count()).select_from(CompanyProblem).where(CompanyProblem.company_id == co.id)) == 3
        rec = {p.external_id: c.recent for c, p in db.execute(select(CompanyProblem, Problem).join(Problem, Problem.id == CompanyProblem.problem_id).where(CompanyProblem.company_id == co.id))}
        assert rec["two-sum"] is True and rec["trapping-rain-water"] is False
        p = db.scalar(select(Problem).where(Problem.platform == "leetcode", Problem.external_id == "trapping-rain-water"))
        assert p.source_difficulty == "Hard" and p.statement_access == "link_only" and p.rating is None


def test_run_with_mock_transport_survives_one_failing_company(client):
    def h(req: httpx.Request):
        u = str(req.url)
        if "api.github.com" in u:
            return httpx.Response(200, json={"tree": [{"path": "Beta Co/5. All.csv"}, {"path": "Gamma Co/5. All.csv"}]})
        if "Gamma" in u:
            return httpx.Response(500)
        if "3.%20Six" in u:
            return httpx.Response(404)
        return httpx.Response(200, text=ALL)
    import time
    orig = time.sleep; time.sleep = lambda s: None
    try:
        with dbmod.SessionLocal() as db:
            rep = cl.run(db, client=httpx.Client(transport=httpx.MockTransport(h)), delay=0, log=lambda *_: None)
    finally:
        time.sleep = orig
    assert rep["companies"] == 1 and rep["failed"] == 1
