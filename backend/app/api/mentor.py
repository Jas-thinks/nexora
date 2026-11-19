import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_role
from app.core.db import get_db
from app.llm.router import Router
from app.models.ai import KnowledgeDoc, LLMCall, MentorMessage, TrainingExample, UserPrefs
from app.models.user import User, utcnow
from app.rag import service as rag
from app.services import mentor

router = APIRouter(tags=["mentor"])


def get_router() -> Router:
    return Router()


class Frame(BaseModel):
    n: int
    note: str = Field(max_length=600)


class Trace(BaseModel):
    algorithm: str = Field("", max_length=60)
    frames: list[Frame] = Field(default_factory=list, max_length=60)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: str = "concept"
    thread: str = Field("default", max_length=40, pattern=r"^[\w\-]+$")
    hint_level: int = Field(1, ge=1, le=5)
    problem_id: int | None = None
    code: str | None = Field(None, max_length=20000)
    trace: Trace | None = None
    design: dict | None = None


@router.get("/mentor/status")
def status(user: User = Depends(current_user), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    st = r.status()
    st["tokens_used_24h"] = mentor._budget_used(db, user.id)
    st["offline"] = not st["configured"]
    st["message"] = None if st["configured"] else "No LLM provider key is configured. The mentor answers from Nexora's own notes only (offline mode)."
    for p in st["providers"].values():
        p.pop("key", None)
    return st


@router.post("/mentor/chat")
def chat(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    try:
        return mentor.chat(db, r, user.id, body.message, body.mode, body.thread, body.hint_level, body.problem_id, body.code,
                           body.trace.model_dump() if body.trace else None, body.design)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except PermissionError as e:
        raise HTTPException(429, str(e)) from None


@router.post("/mentor/chat/stream")
def chat_stream(body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    """SSE: `event: delta` tokens (an unvalidated DRAFT), then `event: final` with the validated, persisted answer that replaces the draft."""
    try:
        prep = mentor.prepare(db, user.id, body.message, body.mode, body.thread, body.hint_level, body.problem_id, body.code,
                              body.trace.model_dump() if body.trace else None, body.design, r)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except PermissionError as e:
        raise HTTPException(429, str(e)) from None

    def sse(event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    def gen():
        from types import SimpleNamespace
        text, prov, model = [], None, None
        try:
            for prov, model, delta in r.stream(db, user.id, prep.msgs, "mentor", prep.max_tokens):
                text.append(delta)
                yield sse("delta", {"text": delta})
        except Exception:  # never leave the client hanging; fall through to finalise what we have
            pass
        res = SimpleNamespace(text="".join(text), provider=prov, model=model) if text else None
        yield sse("final", mentor.finish(db, user.id, prep, res))
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/mentor/history")
def history(thread: str = "default", limit: int = Query(40, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(MentorMessage).where(MentorMessage.user_id == user.id, MentorMessage.thread == thread).order_by(MentorMessage.id.desc()).limit(limit)).all()
    return [{"id": m.id, "role": m.role, "content": m.content, "mode": m.mode, "meta": m.meta, "feedback": m.feedback, "created_at": m.created_at} for m in reversed(rows)]


class FeedbackIn(BaseModel):
    value: int = Field(ge=-1, le=1)


@router.post("/mentor/{mid}/feedback")
def feedback(mid: int, body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(MentorMessage, mid)
    if m is None or m.user_id != user.id or m.role != "assistant":
        raise HTTPException(404, "Message not found")
    m.feedback = body.value or None
    db.commit()
    return {"ok": True}


class PrefsIn(BaseModel):
    training_opt_in: bool | None = None
    leaderboard_visible: bool | None = None
    share_progress: bool | None = None
    experiment_opt_out: bool | None = None
    email_notifications: bool | None = None
    daily_goal: int | None = Field(None, ge=1, le=20)
    weekly_goal: int | None = Field(None, ge=1, le=100)


@router.get("/me/prefs")
def get_prefs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(UserPrefs, user.id)
    return {"training_opt_in": bool(p and p.training_opt_in), "leaderboard_visible": bool(p and p.leaderboard_visible), "share_progress": bool(p and p.share_progress),
            "experiment_opt_out": bool(p and p.experiment_opt_out), "email_notifications": bool(p and p.email_notifications), "daily_goal": p.daily_goal if p else 1, "weekly_goal": p.weekly_goal if p else 5}


@router.put("/me/prefs")
def put_prefs(body: PrefsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(UserPrefs, user.id) or UserPrefs(user_id=user.id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    p.updated_at = utcnow()
    db.add(p); db.commit()
    return get_prefs(user, db)


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=8000)


@router.post("/notes", status_code=201)
def add_note(body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = rag.add_user_note(db, user.id, body.title, body.text)
    return {"id": d.id, "title": d.title}


@router.get("/notes")
def list_notes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": d.id, "title": d.title, "text": d.text} for d in db.scalars(select(KnowledgeDoc).where(KnowledgeDoc.owner_id == user.id).order_by(KnowledgeDoc.id.desc()))]


@router.delete("/notes/{nid}", status_code=204)
def del_note(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDoc, nid)
    if d is None or d.owner_id != user.id:
        raise HTTPException(404, "Note not found")
    db.delete(d); db.commit(); rag._CACHE.clear()


@router.post("/admin/rag/embed")
def embed_docs(_: User = Depends(require_role("admin")), db: Session = Depends(get_db), r: Router = Depends(get_router)):
    out = rag.embed_docs(db, r)
    if out["failed"] and not out["embedded"]:
        raise HTTPException(503, "No embedding provider available (Ollama with an embedding model, or a Gemini key). Retrieval stays keyword-only.")
    return out


@router.post("/admin/rag/ingest")
def ingest(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return rag.ingest_builtin(db)


@router.get("/admin/llm/usage")
def usage(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.execute(select(LLMCall.provider, func.count(), func.sum(LLMCall.ok.cast(__import__("sqlalchemy").Integer)), func.coalesce(func.sum(LLMCall.prompt_tokens), 0),
                             func.coalesce(func.sum(LLMCall.completion_tokens), 0), func.coalesce(func.avg(LLMCall.latency_ms), 0)).group_by(LLMCall.provider)).all()
    return [{"provider": p, "calls": n, "ok": int(ok or 0), "prompt_tokens": int(pt), "completion_tokens": int(ct), "avg_latency_ms": round(float(lat))} for p, n, ok, pt, ct, lat in rows]


@router.get("/admin/training/export", response_class=PlainTextResponse)
def export_training(min_rating: int = 0, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """JSONL in chat format for later fine-tuning. Only consented, non-offline examples exist; no user ids."""
    rows = db.scalars(select(TrainingExample).where((TrainingExample.rating.is_(None)) | (TrainingExample.rating >= min_rating)).order_by(TrainingExample.id))
    return "\n".join(json.dumps({"messages": [{"role": "user", "content": e.prompt}, {"role": "assistant", "content": e.response}], "mode": e.mode}, ensure_ascii=False) for e in rows)


@router.get("/admin/experiments/daily")
def daily_experiment(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    from app.services import experiment
    return experiment.report(db)
