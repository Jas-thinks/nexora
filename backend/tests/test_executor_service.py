import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.execution import remote, runner
from app.execution.service import app as exec_app

REAL = runner.docker_ready() and runner.image_present(runner.LANGS["python"].image)


@pytest.fixture()
def svc(monkeypatch):
    monkeypatch.setenv("CODEMIND_EXECUTOR_KEY", "k-secret"); get_settings.cache_clear()
    yield TestClient(exec_app, headers={"X-Executor-Key": "k-secret"})
    get_settings.cache_clear()


def test_service_rejects_missing_or_wrong_key(svc):
    anon = TestClient(exec_app)
    assert anon.get("/health").status_code == 401 and anon.post("/run", json={"language": "python", "code": "1"}).status_code == 401
    assert TestClient(exec_app, headers={"X-Executor-Key": "nope"}).post("/run", json={"language": "python", "code": "1"}).status_code == 401


def test_service_refuses_when_no_key_is_configured(monkeypatch):
    monkeypatch.delenv("CODEMIND_EXECUTOR_KEY", raising=False); get_settings.cache_clear()
    try:
        assert TestClient(exec_app, headers={"X-Executor-Key": ""}).get("/health").status_code == 401  # an unconfigured service is closed, not open
    finally:
        get_settings.cache_clear()


def test_service_validates_input(svc):
    assert svc.post("/run", json={"language": "python", "code": "x" * 70000}).status_code == 422
    assert svc.post("/judge", json={"language": "python", "code": "1", "tests": [{}] * 41}).status_code == 422


def test_dispatch_uses_remote_only_when_configured_and_degrades_cleanly(monkeypatch):
    monkeypatch.setenv("CODEMIND_EXECUTOR_URL", "http://127.0.0.1:1"); monkeypatch.setenv("CODEMIND_EXECUTOR_KEY", "k"); get_settings.cache_clear()
    try:
        r = runner.run_code("python", "print(1)")  # nothing is listening: must be a clear ERR, not a crash and not a silent local run
        assert r.verdict == "ERR" and "unavailable" in r.note
        a = runner.availability()
        assert a["remote"] and a["docker"] is False and not any(v["ready"] for v in a["languages"].values())
    finally:
        get_settings.cache_clear()


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
def test_remote_client_round_trip_through_the_service(svc):
    r = remote.run_code("python", "print(int(input())*3)", "14", client=svc)
    assert r.verdict == "OK" and r.stdout.strip() == "42"
    j = remote.judge("python", "print(int(input())*2)", [{"input": "2", "expected": "4"}, {"input": "3", "expected": "7"}], client=svc)
    assert j.verdict == "WA" and [t["verdict"] for t in j.tests] == ["OK", "WA"]
    assert remote.availability(client=svc)["languages"]["python"]["ready"] is True


# --- stress testing through the executor (the API container has no Docker) ---------------------------------
STRESS = {"solution_language": "python", "solution_code": "print(1)", "brute_language": "python", "brute_code": "print(1)", "generator_code": "print(1)"}


def test_executor_stress_needs_key(svc):
    assert TestClient(exec_app).post("/stress", json=STRESS).status_code == 401


def test_executor_stress_rejects_unknown_language(svc):
    assert svc.post("/stress", json={**STRESS, "solution_language": "cobol"}).status_code == 422


def test_executor_stress_runs_service(svc, monkeypatch):
    from app.execution import service
    monkeypatch.setattr(service.stress, "run", lambda *a, **k: {"status": "passed", "iterations": 3})
    assert svc.post("/stress", json=STRESS).json() == {"status": "passed", "iterations": 3}


def test_api_forwards_stress_to_remote_executor(client, monkeypatch):
    from tests.conftest import auth, register
    monkeypatch.setattr(get_settings(), "executor_url", "http://executor:9000")
    seen = {}
    monkeypatch.setattr(remote, "stress", lambda p, client=None: seen.update(p) or {"status": "passed"})
    h = auth(register(client))
    assert client.post("/stress", json=STRESS, headers=h).json() == {"status": "passed"} and seen["brute_language"] == "python"


def test_api_maps_remote_stress_errors(client, monkeypatch):
    from tests.conftest import auth, register
    monkeypatch.setattr(get_settings(), "executor_url", "http://executor:9000")
    h = auth(register(client))
    monkeypatch.setattr(remote, "stress", lambda p, client=None: (_ for _ in ()).throw(remote.BusyError()))
    assert client.post("/stress", json=STRESS, headers=h).status_code == 429
    monkeypatch.setattr(remote, "stress", lambda p, client=None: (_ for _ in ()).throw(RuntimeError("The execution backend is unreachable.")))
    assert client.post("/stress", json=STRESS, headers=h).status_code == 503
