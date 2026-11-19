from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.design.review import DOC_SECTIONS, NODE_TYPES, SCENARIOS, review
from app.models.ai import Design
from app.models.user import User, utcnow

router = APIRouter(tags=["design"])


class Node(BaseModel):
    id: str = Field(max_length=40)
    type: str = Field(max_length=30)
    label: str = Field("", max_length=60)
    replicas: int = Field(1, ge=1, le=1000)
    consistency: str | None = Field(None, max_length=20)
    kind: str | None = Field(None, max_length=20)
    x: float = 0
    y: float = 0


class Edge(BaseModel):
    from_: str = Field(alias="from", max_length=40)
    to: str = Field(max_length=40)
    label: str = Field("", max_length=40)
    model_config = {"populate_by_name": True}


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list, max_length=80)
    edges: list[Edge] = Field(default_factory=list, max_length=200)

    def plain(self) -> dict:
        return {"nodes": [n.model_dump() for n in self.nodes], "edges": [{"from": e.from_, "to": e.to, "label": e.label} for e in self.edges]}


_DOC_KEYS = {k for k, _, _ in DOC_SECTIONS}


class DesignIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    scenario: str | None = None
    prompt: str = Field("", max_length=2000)  # ANY system-design question, in the student's own words
    doc: dict[str, str] = Field(default_factory=dict)
    question: str | None = Field(None, max_length=80)
    graph: Graph

    def clean_doc(self) -> dict:
        if set(self.doc) - _DOC_KEYS - {"reviewed"}:
            raise HTTPException(422, f"doc sections must be among {sorted(_DOC_KEYS)}")
        return {k: v[:6000] for k, v in self.doc.items()}


@router.get("/design/scenarios")
def scenarios(user: User = Depends(current_user)):
    return {"scenarios": [{"id": k, "title": v["title"], "prompt": v["prompt"], "expected": v["expected"]} for k, v in SCENARIOS.items()], "node_types": sorted(NODE_TYPES),
            "doc_sections": [{"key": k, "label": l, "hint": h} for k, l, h in DOC_SECTIONS]}


@router.post("/design/review")
def review_graph(body: DesignIn, user: User = Depends(current_user)):
    if body.scenario and body.scenario not in SCENARIOS:
        raise HTTPException(422, "unknown scenario")
    return review(body.graph.plain(), body.scenario, body.prompt, body.clean_doc())


@router.get("/design")
def list_designs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": d.id, "title": d.title, "scenario": d.scenario, "question": d.question, "updated_at": d.updated_at, "nodes": len(d.graph.get("nodes", [])), "reviewed": bool((d.doc or {}).get("reviewed"))}
            for d in db.scalars(select(Design).where(Design.user_id == user.id).order_by(Design.updated_at.desc()))]


@router.post("/design", status_code=201)
def create(body: DesignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.scenario and body.scenario not in SCENARIOS:
        raise HTTPException(422, "unknown scenario")
    if len(db.scalars(select(Design.id).where(Design.user_id == user.id)).all()) >= 50:
        raise HTTPException(409, "Design limit reached (50)")
    d = Design(user_id=user.id, title=body.title, scenario=body.scenario, graph=body.graph.plain(), prompt=body.prompt, doc=body.clean_doc(), question=body.question)
    db.add(d); db.commit()
    return {"id": d.id}


def _own(db: Session, user: User, did: int) -> Design:
    d = db.get(Design, did)
    if d is None or d.user_id != user.id:
        raise HTTPException(404, "Design not found")
    return d


@router.get("/design/{did}")
def get(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _own(db, user, did)
    return {"id": d.id, "title": d.title, "scenario": d.scenario, "prompt": d.prompt, "doc": d.doc or {}, "question": d.question, "graph": d.graph, "updated_at": d.updated_at}


@router.put("/design/{did}")
def update(did: int, body: DesignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _own(db, user, did)
    keep = {"reviewed": True} if (d.doc or {}).get("reviewed") else {}
    d.title, d.scenario, d.graph, d.prompt, d.doc, d.question, d.updated_at = body.title, body.scenario, body.graph.plain(), body.prompt, {**body.clean_doc(), **keep}, body.question, utcnow()
    db.commit()
    return {"saved": True}


@router.delete("/design/{did}", status_code=204)
def delete(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, did)); db.commit()


@router.post("/design/{did}/reviewed")
def mark_reviewed(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Progress marker (shown in the question library) after the student has run an AI review on this design."""
    d = _own(db, user, did)
    d.doc = {**(d.doc or {}), "reviewed": True}
    db.commit()
    return {"reviewed": True}
