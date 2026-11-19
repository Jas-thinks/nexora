from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core import db as dbmod
from app.models.integrations import Submission
from app.services import capture

NOW = datetime.now(UTC)
def item(i, verdict="Accepted", slug="two-sum", at=None, **kw):
    return {"id": str(i), "problem_url": f"https://leetcode.com/problems/{slug}/description/", "verdict": verdict, "submitted_at": (at or NOW - timedelta(hours=1)).isoformat(), "language": "python3", **kw}


def reg(client, email="cap@example.com"):
    t = client.post("/auth/register", json={"email": email, "display_name": "c", "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def mk_token(client, h):
    return client.post("/capture/tokens", headers=h, json={"label": "laptop"}).json()["token"]


def test_verdict_normalisation_never_guesses():
    assert capture.normalise_verdict("Accepted") == "AC" and capture.normalise_verdict("Time Limit Exceeded") == "TLE"
    assert capture.normalise_verdict("Runtime Error (NZEC)") == "RE" and capture.normalise_verdict("Internal Error") == "OTHER"
    assert capture.normalise_verdict("Pending") is None and capture.normalise_verdict("") is None


def test_parse_rejects_bad_rows_with_reasons():
    ok, errs = capture.parse("leetcode", [item(1), item(2, slug="x", at=NOW + timedelta(days=2)), item(3, verdict="Judging"),
                                          {**item(4), "problem_url": "https://codeforces.com/problemset/problem/1/A"}, {"verdict": "Accepted"}], NOW)
    assert [o.external_id for o in ok] == ["1"] and ok[0].provenance == "extension" and ok[0].problem_ref == "two-sum"
    msgs = " | ".join(e["error"] for e in errs)
    assert "future" in msgs and "not judged" in msgs and "codeforces problem" in msgs and len(errs) == 4


def test_token_lifecycle_and_scope(client):
    h = reg(client)
    tok = mk_token(client, h)
    assert tok.startswith("nxc_")
    listed = client.get("/capture/tokens", headers=h).json()
    assert len(listed) == 1 and "token" not in listed[0] and listed[0]["prefix"] == tok[:10]
    # the capture token is NOT a user session: it cannot read anything
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    assert client.get("/capture/tokens", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    # a user JWT cannot upload either
    assert client.post("/capture/submissions", headers=h, json={"platform": "leetcode", "submissions": [item(1)]}).status_code == 401
    assert client.delete(f"/capture/tokens/{listed[0]['id']}", headers=h).status_code == 204
    assert client.post("/capture/submissions", headers={"Authorization": f"Bearer {tok}"}, json={"platform": "leetcode", "submissions": [item(1)]}).status_code == 401


def test_cannot_revoke_someone_elses_token(client):
    a, b = reg(client, "a@example.com"), reg(client, "b@example.com")
    mk_token(client, a)
    tid = client.get("/capture/tokens", headers=a).json()[0]["id"]
    assert client.delete(f"/capture/tokens/{tid}", headers=b).status_code == 404
    assert client.get("/capture/tokens", headers=a).json()[0]["revoked"] is False


def test_upload_is_idempotent_labelled_and_attributed_to_token_owner(client):
    h = reg(client); tok = mk_token(client, h); th = {"Authorization": f"Bearer {tok}"}
    body = {"platform": "leetcode", "submissions": [item(11, "Wrong Answer"), item(12, "Accepted"), item(13, "Pending")]}
    r = client.post("/capture/submissions", headers=th, json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["added"] == 2 and j["duplicates"] == 0 and j["rejected_count"] == 1 and "not verified" in j["label"]
    assert client.post("/capture/submissions", headers=th, json=body).json()["added"] == 0  # retry-safe
    with dbmod.SessionLocal() as db:
        subs = db.scalars(select(Submission).where(Submission.platform == "leetcode")).all()
        assert {s.provenance for s in subs} == {"extension"} and {s.verdict for s in subs} == {"WA", "AC"}
    assert client.get("/capture/tokens", headers=h).json()[0]["last_used_at"] is not None


def test_unknown_platform_and_oversize_batch(client):
    h = reg(client); th = {"Authorization": f"Bearer {mk_token(client, h)}"}
    assert client.post("/capture/submissions", headers=th, json={"platform": "nope", "submissions": [item(1)]}).status_code == 422
    big = {"platform": "leetcode", "submissions": [item(i) for i in range(capture.MAX_BATCH + 1)]}
    assert client.post("/capture/submissions", headers=th, json=big).status_code == 422


def test_five_token_cap(client):
    h = reg(client)
    for _ in range(5):
        assert client.post("/capture/tokens", headers=h, json={}).status_code == 201
    assert client.post("/capture/tokens", headers=h, json={}).status_code == 409
