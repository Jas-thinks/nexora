"""RAG: ingest -> chunk -> index -> hybrid retrieve (BM25 + metadata boost) -> context assembly with source attribution.
Embeddings are NOT used yet (needs a provider key / pgvector); the interface leaves room: add a vector score and fuse with RRF."""
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.ai import KnowledgeDoc
from app.models.user import utcnow
from app.patterns.taxonomy import BY_ID, PATTERNS
from app.rag.bm25 import BM25, tokenize
from app.rag.design_notes import DESIGN_NOTES
from app.rag.notes import NOTES

INJECTION = re.compile(r"(ignore (all |any |the )?(previous|prior|above) (instructions|prompts?)|disregard .{0,30}instructions|system prompt|you are now|act as)", re.I)
_CACHE: dict = {}


@dataclass
class Hit:
    key: str
    title: str
    text: str
    url: str | None
    kind: str
    score: float


def sanitize(text: str) -> str:
    """Retrieved/user text is DATA. Lines that try to instruct the model are removed before they reach the prompt."""
    return "\n".join(ln for ln in text.splitlines() if not INJECTION.search(ln))[:4000]


def ingest_builtin(db: Session) -> dict:
    added = updated = 0
    docs = [dict(key=n["key"], kind="note", title=n["title"], text=n["text"], url=None, meta={"patterns": n["patterns"], "license": "project", "review": "unreviewed"}) for n in NOTES + DESIGN_NOTES]
    for p in PATTERNS:
        if p.kind == "category":
            continue
        rel = lambda ids: ", ".join(BY_ID[i].name for i in ids if i in BY_ID)
        t = f"{p.name} ({p.kind.replace('_', ' ')}; category {BY_ID[p.parent].name if p.parent else '-'}).\n"
        if p.clues: t += "Recognise it: " + "; ".join(p.clues) + ".\n"
        if p.complexity: t += f"Complexity: {p.complexity}.\n"
        if p.prereq: t += f"Prerequisites: {rel(p.prereq)}.\n"
        if p.extends: t += f"Extends: {rel(p.extends)}.\n"
        if p.contrasts: t += f"Looks similar but is different from: {rel(p.contrasts)}.\n"
        if p.related: t += f"Related: {rel(p.related)}.\n"
        docs.append(dict(key=f"pattern:{p.id}", kind="pattern", title=p.name, text=t, url=None, meta={"patterns": [p.id], "license": "project"}))
    for d in docs:
        row = db.scalar(select(KnowledgeDoc).where(KnowledgeDoc.key == d["key"]))
        if row is None:
            db.add(KnowledgeDoc(**d)); added += 1
        elif (row.text, row.title) != (d["text"], d["title"]):
            row.text, row.title, row.meta, row.updated_at = d["text"], d["title"], d["meta"], utcnow(); updated += 1
    db.commit()
    _CACHE.clear()
    return {"added": added, "updated": updated, "total": len(docs)}


def add_user_note(db: Session, user_id: int, title: str, text: str) -> KnowledgeDoc:
    import hashlib
    key = f"user:{user_id}:{hashlib.sha1((title + text).encode()).hexdigest()[:10]}"
    row = db.scalar(select(KnowledgeDoc).where(KnowledgeDoc.key == key))
    if row is None:
        row = KnowledgeDoc(key=key, kind="user_note", title=title[:200], text=text[:8000], owner_id=user_id, meta={"license": "owned by user"})
        db.add(row); db.commit(); _CACHE.clear()
    return row


def _index(db: Session, user_id: int | None):
    ver = (db.scalar(select(KnowledgeDoc.updated_at).order_by(KnowledgeDoc.updated_at.desc()).limit(1)), db.query(KnowledgeDoc).count(), user_id)
    if _CACHE.get("ver") == ver:
        return _CACHE["idx"]
    docs = list(db.scalars(select(KnowledgeDoc).where(or_(KnowledgeDoc.owner_id.is_(None), KnowledgeDoc.owner_id == user_id))))
    idx = (docs, BM25([tokenize(d.title + " " + d.title + " " + d.text) for d in docs]))  # title counted twice: cheap field boost
    _CACHE.update(ver=ver, idx=idx)
    return idx


def embed_docs(db: Session, router, batch: int = 16) -> dict:
    """Compute embeddings for docs that lack one (or have one from a different model). Safe to re-run."""
    todo = list(db.scalars(select(KnowledgeDoc)))
    done = failed = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        res = router.embed([d.title + ". " + d.text[:1500] for d in chunk])
        if res is None:
            failed += len(chunk); continue
        vecs, model = res
        for d, v in zip(chunk, vecs):
            if d.embedding is None or d.embed_model != model:
                d.embedding, d.embed_model = v, model; done += 1
    db.commit(); _CACHE.clear()
    return {"embedded": done, "failed": failed, "total": len(todo)}


def _cos(a, b) -> float:
    import math
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def retrieve(db: Session, query: str, user_id: int | None = None, k: int = 4, boost_patterns: list[str] | None = None, router=None) -> list[Hit]:
    docs, bm = _index(db, user_id)
    if not docs:
        return []
    q = tokenize(query)
    scores = bm.score(q)
    out = []
    for d, s in zip(docs, scores):
        if d.owner_id is not None and d.owner_id != user_id:
            continue  # never cross users
        if boost_patterns and set(d.meta.get("patterns", [])) & set(boost_patterns):
            s += 1.5
        if s > 0:
            out.append(Hit(d.key, d.title, sanitize(d.text), d.url, d.kind, round(s, 3)))
    out.sort(key=lambda h: -h.score)
    if router is None or not any(d.embedding for d in docs):
        return out[:k]
    # hybrid: reciprocal-rank fusion of BM25 order and cosine order (only if the query can be embedded with the same model as the docs)
    emb = router.embed([query])
    if emb is None:
        return out[:k]
    qv, model = emb[0][0], emb[1]
    cands = [(d, _cos(qv, d.embedding)) for d in docs if d.embedding and d.embed_model == model and (d.owner_id is None or d.owner_id == user_id)]
    if not cands:
        return out[:k]
    sem = sorted(cands, key=lambda x: -x[1])
    rrf: dict[str, float] = {}
    for rank, h in enumerate(out, 1):
        rrf[h.key] = rrf.get(h.key, 0) + 1 / (60 + rank)
    for rank, (d, _) in enumerate(sem, 1):
        rrf[d.key] = rrf.get(d.key, 0) + 1 / (60 + rank)
    by = {h.key: h for h in out} | {d.key: Hit(d.key, d.title, sanitize(d.text), d.url, d.kind, 0.0) for d, _ in sem[:k * 3]}
    fused = sorted((key for key in rrf if key in by), key=lambda key: -rrf[key])
    return [Hit(by[key].key, by[key].title, by[key].text, by[key].url, by[key].kind, round(rrf[key] * 100, 3)) for key in fused[:k]]
