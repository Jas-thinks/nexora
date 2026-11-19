import pytest
from sqlalchemy import select

from app.core import db as dbmod
from app.llm.router import Router
from app.models.ai import ProblemPatternLabel
from app.models.catalog import Problem
from app.models.user import User
from app.patterns import labeling, mastery
from tests.conftest import auth, register
from tests.test_mentor import Fake


def mkp(db, ext, name, tags=(), rating=1500):
    p = Problem(platform="codeforces", external_id=ext, name=name, rating=rating, tags=list(tags), url="u", canonical_url="u")
    db.add(p); db.flush(); return p


def test_title_and_combo_rules_propose_fine_patterns_with_reasons(client):
    with dbmod.SessionLocal() as db:
        k = mkp(db, "1", "Knapsack with Huge Weights", ["dp"])
        t = mkp(db, "2", "Sum over Tree Paths", ["dp", "trees"])
        b = mkp(db, "3", "Assign Tasks", ["binary search", "greedy"])
        n = mkp(db, "4", "Plain Problem", ["math"])
        got = lambda p: {x[0]: x for x in labeling.rule_proposals(p)}
        assert "knapsack" in got(k) and got(k)["knapsack"][1] >= 0.9 and "knapsack" in got(k)["knapsack"][2].lower()
        assert got(t)["tree-dp"][1] == pytest.approx(0.65) and got(b)["binary-search-answer"][1] == pytest.approx(0.5)
        assert labeling.rule_proposals(n) == []


def test_only_explicit_keyword_rules_auto_accept_everything_else_waits_for_review(client):
    with dbmod.SessionLocal() as db:
        mkp(db, "1", "Knapsack Again", ["dp"]); mkp(db, "2", "Tree thing", ["dp", "trees"])
        r = labeling.propose_rules(db)
        st = {l.pattern_id: l.status for l in db.scalars(select(ProblemPatternLabel))}
        assert r["auto_accepted"] == 1 and st["knapsack"] == "accepted" and st["tree-dp"] == "proposed"


def test_proposals_never_overwrite_existing_decisions_and_are_idempotent(client):
    with dbmod.SessionLocal() as db:
        p = mkp(db, "1", "Tree thing", ["dp", "trees"])
        labeling.propose_rules(db)
        l = db.scalar(select(ProblemPatternLabel)); l.status = "rejected"; db.commit()
        assert labeling.propose_rules(db)["proposals_added"] == 0
        assert db.scalar(select(ProblemPatternLabel.status)) == "rejected"


def test_only_accepted_labels_become_mastery_evidence_and_make_patterns_measurable(client):
    register(client)
    with dbmod.SessionLocal() as db:
        uid = db.scalar(select(User.id))
        ps = [mkp(db, f"k{i}", f"Problem {i}", ["dp"], 1200) for i in range(4)]
        from app.models.integrations import Submission
        from datetime import UTC, datetime
        for p in ps:
            db.add(Submission(user_id=uid, platform="codeforces", external_id=f"s{p.id}", problem_ref=p.external_id, problem_id=p.id, verdict="WA", submitted_at=datetime.now(UTC)))
            db.add(ProblemPatternLabel(problem_id=p.id, pattern_id="knapsack", source="llm", confidence=.7, status="proposed"))
        db.commit()
        mastery.bump_catalog()
        assert mastery.assess_all(db, uid)["knapsack"].status == "unmeasured"
        for l in db.scalars(select(ProblemPatternLabel)): l.status = "accepted"
        db.commit(); mastery.bump_catalog()
        st = mastery.assess_all(db, uid)["knapsack"]
        assert st.status in ("weak", "learning") and st.attempted == 4


def test_llm_output_parsing_is_strict_and_confidence_capped_and_never_auto_accepts(client):
    assert labeling.parse_llm('x {"patterns":[{"id":"knapsack","confidence":0.9,"reason":"w"},{"id":"made-up","confidence":0.9},{"id":"algorithms","confidence":1}]} y') == [("knapsack", 0.9, "w")]
    assert labeling.parse_llm("not json") == [] and labeling.parse_llm('{"patterns": "oops"}') == []
    assert labeling.parse_llm('{"patterns":[{"id":"dsu","confidence":5}]}') == []  # out-of-range confidence rejected
    with dbmod.SessionLocal() as db:
        p = mkp(db, "1", "Some Problem", ["dp"])
        r = Router({"f": Fake("f", reply='{"patterns":[{"id":"knapsack","confidence":0.99,"reason":"subset under capacity"}]}')}, ["f"])
        assert labeling.propose_llm(db, r, [p.id])["proposals_added"] == 1
        l = db.scalar(select(ProblemPatternLabel))
        assert l.source == "llm" and l.status == "proposed" and l.confidence == 0.85
        assert labeling.propose_llm(db, Router({}, []), [p.id])["no_proposal"] == 1


def test_prompt_contains_metadata_only(client):
    with dbmod.SessionLocal() as db:
        p = mkp(db, "1", "Some Problem", ["dp"], 1700)
        f = Fake("f", reply="{}"); labeling.llm_proposals(Router({"f": f}, ["f"]), p)
    prompt = f.calls[0][0]["content"]
    assert "Some Problem" in prompt and "1700" in prompt and "statement" in prompt.lower() and "knapsack: " in prompt


def test_review_api_roles_stats_and_human_labels(client):
    t = register(client); h = auth(t)
    with dbmod.SessionLocal() as db:
        p = mkp(db, "1", "Tree thing", ["dp", "trees"]); labeling.propose_rules(db); pid = p.id
    assert client.get("/labels/queue", headers=h).status_code == 403  # students cannot review
    with dbmod.SessionLocal() as db:
        u = db.scalar(select(User)); u.role = "moderator"; db.commit()
    q = client.get("/labels/queue", headers=h).json()
    assert q[0]["pattern"] == "tree-dp" and q[0]["problem"]["name"] == "Tree thing" and q[0]["reason"]
    assert client.post(f"/labels/{q[0]['id']}/review", headers=h, json={"decision": "accept", "note": "ok"}).json()["status"] == "accepted"
    assert client.post(f"/labels/{q[0]['id']}/review", headers=h, json={"decision": "maybe"}).status_code == 422
    assert client.post("/labels", headers=h, json={"problem_id": pid, "pattern_id": "dp-2d"}).status_code == 201
    assert client.post("/labels", headers=h, json={"problem_id": pid, "pattern_id": "algorithms"}).status_code == 422
    s = client.get("/labels/stats", headers=h).json()
    assert s["by_source_status"]["rule/accepted"] == 1 and s["by_source_status"]["human/accepted"] == 1
    assert s["measurable_patterns"]["with_accepted_labels"] > s["measurable_patterns"]["before_labels"] - 1 and s["proposer_precision_from_human_review"]["rule"] is None
    assert client.post("/admin/labels/propose", headers=h, json={"source": "rule"}).status_code == 403
