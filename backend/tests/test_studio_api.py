import pytest

from app.execution import runner
from tests.conftest import auth, register

REAL = runner.docker_ready() and all(runner.image_present(l.image) for l in runner.LANGS.values())


@pytest.fixture()
def env(client):
    return client, auth(register(client))


def test_requires_auth_and_validates_language_and_size(env):
    c, h = env
    assert c.post("/execute", json={"language": "python", "code": "1"}).status_code == 401
    assert c.post("/execute", headers=h, json={"language": "cobol", "code": "x"}).status_code == 422
    assert c.post("/execute", headers=h, json={"language": "python", "code": "x" * 70000}).status_code == 422
    assert c.post("/execute", headers=h, json={"language": "python", "code": "1", "tests": [{"input": "", "expected": ""}] * 21}).status_code == 422


def test_degrades_to_503_when_docker_is_unavailable(env, monkeypatch):
    c, h = env
    monkeypatch.setattr(runner, "docker_ready", lambda: False)
    assert c.post("/execute", headers=h, json={"language": "python", "code": "print(1)"}).status_code == 503
    assert c.get("/execute/languages", headers=h).json()["docker"] is False


def test_rate_limit_and_backpressure(env, monkeypatch):
    c, h = env
    from app.api import studio
    monkeypatch.setattr(runner, "run_code", lambda *a, **k: runner.RunResult("OK", stdout="1"))
    codes = [c.post("/execute", headers=h, json={"language": "python", "code": "1"}).status_code for _ in range(22)]
    assert codes[:20] == [200] * 20 and codes[20:] == [429, 429]
    from app.core.ratelimit import limiter
    limiter.hits.clear()
    for _ in range(4): studio._SLOTS.acquire()
    try:
        assert c.post("/execute", headers=h, json={"language": "python", "code": "1"}).status_code == 429
    finally:
        for _ in range(4): studio._SLOTS.release()


def test_drafts_persist_per_user_key_and_language_and_validate_keys(env):
    c, h = env
    assert c.put("/drafts/scratch", headers=h, json={"language": "python", "code": "print(1)"}).status_code == 200
    c.put("/drafts/scratch", headers=h, json={"language": "python", "code": "print(2)"})
    assert c.get("/drafts/scratch?language=python", headers=h).json()["code"] == "print(2)"
    assert c.get("/drafts/scratch?language=cpp17", headers=h).json()["code"] is None
    assert c.put("/drafts/../etc", headers=h, json={"language": "python", "code": "x"}).status_code in (404, 422)
    assert c.put("/drafts/problem:abc", headers=h, json={"language": "python", "code": "x"}).status_code == 422
    other = auth(register(c, "b@example.com"))
    assert c.get("/drafts/scratch?language=python", headers=other).json()["code"] is None  # isolation


@pytest.mark.skipif(not REAL, reason="Docker + images required")
def test_real_run_judge_and_history(env):
    c, h = env
    r = c.post("/execute", headers=h, json={"language": "python", "code": "print(int(input())+1)", "stdin": "41"}).json()
    assert r["verdict"] == "OK" and r["stdout"].strip() == "42" and r["memory_kb"] is None
    j = c.post("/execute", headers=h, json={"language": "python", "code": "print(int(input())*2)", "tests": [{"input": "2", "expected": "4"}, {"input": "3", "expected": "7"}]}).json()
    assert j["verdict"] == "WA" and [t["verdict"] for t in j["tests"]] == ["OK", "WA"]
    hist = c.get("/runs", headers=h).json()
    assert [x["kind"] for x in hist] == ["judge", "run"]
