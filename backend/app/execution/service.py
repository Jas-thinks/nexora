"""Standalone executor service: run this on a SEPARATE host/VM that has Docker, and point the API at it with CODEMIND_EXECUTOR_URL.
The API host then needs no Docker access at all. Authenticated with a shared secret (X-Executor-Key); put it behind a private network."""
import hmac
import threading

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.execution import runner
from app.services import stress

app = FastAPI(title="Nexora executor", docs_url=None, redoc_url=None)


def _auth(x_executor_key: str = Header("")):
    key = get_settings().executor_key
    if not key or not hmac.compare_digest(x_executor_key, key):
        raise HTTPException(401, "bad executor key")


class RunIn(BaseModel):
    language: str
    code: str = Field(max_length=runner.MAX_CODE)
    stdin: str = Field("", max_length=runner.MAX_STDIN)


class JudgeIn(BaseModel):
    language: str
    code: str = Field(max_length=runner.MAX_CODE)
    tests: list[dict] = Field(max_length=40)


def _out(r: runner.RunResult) -> dict:
    return {"verdict": r.verdict, "stdout": r.stdout, "stderr": r.stderr, "exit_code": r.exit_code, "wall_ms": r.wall_ms, "compile_ms": r.compile_ms,
            "truncated": r.truncated, "note": r.note, "tests": r.tests}


@app.get("/health")
def health(_: None = Depends(_auth)):
    return runner.local_availability()


@app.post("/run")
def run(b: RunIn, _: None = Depends(_auth)):
    return _out(runner.local_run_code(b.language, b.code, b.stdin))


@app.post("/judge")
def judge(b: JudgeIn, _: None = Depends(_auth)):
    return _out(runner.local_judge(b.language, b.code, b.tests))


_STRESS_SLOTS = threading.BoundedSemaphore(2)


class StressIn(BaseModel):
    solution_language: str
    solution_code: str = Field(max_length=runner.MAX_CODE)
    brute_language: str
    brute_code: str = Field(max_length=runner.MAX_CODE)
    generator_code: str = Field(max_length=runner.MAX_CODE)
    max_size: int = Field(8, ge=1, le=30)
    iterations: int = Field(120, ge=1, le=400)


@app.post("/stress")
def stress_run(b: StressIn, _: None = Depends(_auth)):
    for lang in (b.solution_language, b.brute_language):
        if lang not in runner.LANGS:
            raise HTTPException(422, "unknown language")
    if not _STRESS_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "executor busy", headers={"Retry-After": "3"})
    try:
        return stress.run((b.solution_language, b.solution_code), (b.brute_language, b.brute_code), ("python", b.generator_code), b.max_size, 40.0, b.iterations)
    finally:
        _STRESS_SLOTS.release()
