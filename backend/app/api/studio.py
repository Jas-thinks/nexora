import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.execution import runner
from app.models.ai import CodeDraft, CodeRun
from app.models.user import User, utcnow

router = APIRouter(tags=["studio"])
_SLOTS = threading.BoundedSemaphore(4)  # at most 4 concurrent containers per API process (backpressure)


class Test(BaseModel):
    input: str = Field("", max_length=20000)
    expected: str = Field("", max_length=20000)


class RunIn(BaseModel):
    language: str
    code: str = Field(max_length=runner.MAX_CODE)
    stdin: str = Field("", max_length=runner.MAX_STDIN)
    tests: list[Test] | None = Field(None, max_length=20)
    problem_id: int | None = None


@router.get("/execute/languages")
def languages(user: User = Depends(current_user)):
    av = runner.availability()
    return {**av, "limits": {k: runner.LIMITS[k] for k in ("time_s", "memory_mb", "out_bytes", "pids")},
            "templates": {k: v.template for k, v in runner.LANGS.items()}, "monaco": {k: v.monaco for k, v in runner.LANGS.items()},
            "note": "Runs happen in isolated, network-less containers. Time is wall-clock including container start-up; peak memory is not measured."}


@router.post("/execute")
def execute(body: RunIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.language not in runner.LANGS:
        raise HTTPException(422, f"language must be one of {list(runner.LANGS)}")
    limiter.check(f"exec:{user.id}", 20, 60.0)  # 20 runs / minute / user
    if not _SLOTS.acquire(blocking=False):
        raise HTTPException(429, "The execution workers are busy. Try again in a few seconds.", headers={"Retry-After": "3"})
    try:
        res = runner.judge(body.language, body.code, [t.model_dump() for t in body.tests]) if body.tests else runner.run_code(body.language, body.code, body.stdin)
    finally:
        _SLOTS.release()
    if res.verdict == "ERR" and "unavailable" in res.note:
        raise HTTPException(503, res.note)
    try:
        from app.core.observability import SANDBOX
        SANDBOX.labels(body.language, res.verdict).inc()
    except Exception:  # noqa: BLE001
        pass
    db.add(CodeRun(user_id=user.id, problem_id=body.problem_id, language=body.language, code=body.code[:runner.MAX_CODE], verdict=res.verdict, wall_ms=res.wall_ms,
                   kind="judge" if body.tests else "run"))
    db.commit()
    return {"verdict": res.verdict, "stdout": res.stdout, "stderr": res.stderr, "exit_code": res.exit_code, "wall_ms": res.wall_ms, "compile_ms": res.compile_ms,
            "truncated": res.truncated, "note": res.note, "memory_kb": None, "tests": res.tests}


class DraftIn(BaseModel):
    language: str
    code: str = Field(max_length=runner.MAX_CODE)


def _key(k: str) -> str:
    if k != "scratch" and not (k.startswith("problem:") and k[8:].isdigit()):
        raise HTTPException(422, "key must be 'scratch' or 'problem:<id>'")
    return k


@router.put("/drafts/{key}")
def save_draft(key: str, body: DraftIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    key = _key(key)
    if body.language not in runner.LANGS:
        raise HTTPException(422, "unknown language")
    d = db.scalar(select(CodeDraft).where(CodeDraft.user_id == user.id, CodeDraft.key == key, CodeDraft.language == body.language))
    if d is None:
        d = CodeDraft(user_id=user.id, key=key, language=body.language, code=body.code); db.add(d)
    d.code, d.updated_at = body.code, utcnow()
    db.commit()
    return {"saved": True, "updated_at": d.updated_at}


@router.get("/drafts/{key}")
def get_draft(key: str, language: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.scalar(select(CodeDraft).where(CodeDraft.user_id == user.id, CodeDraft.key == _key(key), CodeDraft.language == language))
    return {"code": d.code if d else None, "updated_at": d.updated_at if d else None}


@router.get("/runs")
def runs(problem_id: int | None = None, limit: int = 20, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(CodeRun).where(CodeRun.user_id == user.id)
    if problem_id:
        q = q.where(CodeRun.problem_id == problem_id)
    return [{"id": r.id, "language": r.language, "verdict": r.verdict, "wall_ms": r.wall_ms, "kind": r.kind, "created_at": r.created_at, "code": r.code}
            for r in db.scalars(q.order_by(CodeRun.id.desc()).limit(min(limit, 100)))]
