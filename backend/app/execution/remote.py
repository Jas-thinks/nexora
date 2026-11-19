import httpx

from app.core.config import get_settings


def _client():
    return httpx.Client(base_url=get_settings().executor_url, headers={"X-Executor-Key": get_settings().executor_key}, timeout=120)


def _result(d: dict):
    from app.execution.runner import RunResult
    return RunResult(d["verdict"], d["stdout"], d["stderr"], d["exit_code"], d["wall_ms"], d["compile_ms"], d["truncated"], d["note"], tests=d["tests"])


def _post(path: str, payload: dict, client=None):
    from app.execution.runner import RunResult
    try:
        with (client or _client()) as c:
            r = c.post(path, json=payload)
    except httpx.HTTPError:
        return RunResult("ERR", note="Execution backend unavailable (the remote executor could not be reached).")
    if r.status_code != 200:
        return RunResult("ERR", note="Execution backend unavailable (the remote executor rejected the request).")
    return _result(r.json())


def run_code(language, code, stdin="", client=None):
    return _post("/run", {"language": language, "code": code, "stdin": stdin}, client)


def judge(language, code, tests, client=None):
    return _post("/judge", {"language": language, "code": code, "tests": tests}, client)


def availability(client=None) -> dict:
    from app.execution.runner import LANGS
    try:
        with (client or _client()) as c:
            r = c.get("/health")
        if r.status_code == 200:
            return {**r.json(), "remote": True}
    except httpx.HTTPError:
        pass
    return {"docker": False, "remote": True, "languages": {k: {"name": v.name, "ready": False} for k, v in LANGS.items()}}


def stress(payload: dict, client=None) -> dict:
    """Stress test on the executor host (compile once, hundreds of sandboxed runs there). Raises on transport/limit problems so the API can map them."""
    try:
        with (client or _client()) as c:
            r = c.post("/stress", json=payload)
    except httpx.HTTPError as e:
        raise RuntimeError("The execution backend is unreachable.") from e
    if r.status_code == 429:
        raise BusyError()
    if r.status_code != 200:
        raise RuntimeError("The execution backend rejected the request.")
    return r.json()


class BusyError(Exception):
    pass
