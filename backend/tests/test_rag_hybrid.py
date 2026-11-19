import httpx
import pytest

from app.core import db as dbmod
from app.llm.providers import LLMError, OpenAICompat, Provider
from app.llm.router import Router
from app.models.ai import KnowledgeDoc
from app.rag import service as rag


class Emb(Provider):
    """Toy 'semantic' embedder: concept axes. 'merge components' and 'union find' share the connectivity axis; BM25 sees no shared words."""
    name, model, embed_model = "emb", "m", "toy"
    AX = {"connect": ["union", "components", "connectivity", "merge", "group"], "sort": ["sort", "order", "arrange"], "path": ["route", "path", "shortest"]}

    def available(self): return True
    def can_embed(self): return True
    def embed(self, texts, timeout=0):
        return [[float(any(w in t.lower() for w in ws)) + 0.01 for ws in self.AX.values()] for t in texts]
    def chat(self, *a, **k): raise LLMError("no chat")


@pytest.fixture()
def db(client):
    with dbmod.SessionLocal() as s:
        s.add_all([KnowledgeDoc(key="d:dsu", kind="note", title="Union find structure", text="Union find keeps disjoint groups; connectivity queries."),
                   KnowledgeDoc(key="d:sort", kind="note", title="Sorting basics", text="Sort arrays to arrange order."),
                   KnowledgeDoc(key="d:path", kind="note", title="Routing", text="Shortest path routes in graphs.")]); s.commit()
        yield s


def test_bm25_misses_a_paraphrase_that_hybrid_recovers(db):
    q = "combine groups of linked nodes"  # no word overlap with the DSU doc's title/body except 'groups'... use a query with zero overlap:
    q = "linked nodes merge components"
    assert "d:dsu" not in [h.key for h in rag.retrieve(db, "nodes linked", k=1)]
    r = Router({"emb": Emb()}, ["emb"])
    assert rag.embed_docs(db, r) == {"embedded": 3, "failed": 0, "total": 3}
    assert rag.retrieve(db, q, k=1, router=r)[0].key == "d:dsu"


def test_embed_docs_is_idempotent_and_reembeds_when_the_model_changes(db):
    r = Router({"emb": Emb()}, ["emb"])
    assert rag.embed_docs(db, r)["embedded"] == 3 and rag.embed_docs(db, r)["embedded"] == 0
    e = Emb(); e.embed_model = "toy2"
    assert rag.embed_docs(db, Router({"emb": e}, ["emb"]))["embedded"] == 3


def test_without_an_embedder_retrieval_falls_back_to_keyword_search(db):
    r = Router({}, [])
    assert rag.embed_docs(db, r)["failed"] == 3
    assert [h.key for h in rag.retrieve(db, "shortest path routes", k=1, router=r)] == ["d:path"]


def test_vectors_from_a_different_model_are_never_compared(db):
    r = Router({"emb": Emb()}, ["emb"]); rag.embed_docs(db, r)
    other = Emb(); other.embed_model = "other"
    hits = rag.retrieve(db, "shortest path routes", k=2, router=Router({"emb": other}, ["emb"]))
    assert hits and hits[0].key == "d:path"  # fell back to BM25 instead of mixing incompatible vector spaces


def test_user_notes_embeddings_stay_private(db):
    r = Router({"emb": Emb()}, ["emb"])
    from app.models.user import User
    other = User(email="other-notes@example.com", display_name="o", password_hash="x"); db.add(other); db.flush()
    db.add(KnowledgeDoc(key=f"user:{other.id}:x", kind="user_note", title="secret groups", text="merge components trick", owner_id=other.id)); db.commit()
    rag.embed_docs(db, r)
    assert all(h.kind != "user_note" for h in rag.retrieve(db, "merge components", user_id=other.id + 1000, k=5, router=r))


def test_openai_compat_embedding_wire_format_and_errors():
    seen = {}
    def h(req):
        import json
        seen["body"] = json.loads(req.content); seen["url"] = str(req.url)
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]})
    p = OpenAICompat("ollama", "http://x/v1", "", "chat", needs_key=False, transport=httpx.MockTransport(h)); p.embed_model = "nomic-embed-text"
    assert p.embed(["a", "b"]) == [[1, 0], [0, 1]] and seen["url"].endswith("/embeddings") and seen["body"]["model"] == "nomic-embed-text"
    bad = OpenAICompat("g", "http://x", "k", "m", transport=httpx.MockTransport(lambda r: httpx.Response(500, json={}))); bad.embed_model = "e"
    with pytest.raises(LLMError):
        bad.embed(["a"])


def test_local_chat_never_selects_an_installed_embedding_model():
    seen = {}
    def h(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "nomic-embed-text:latest"}, {"id": "gemma3:4b"}]})
        import json
        seen["model"] = json.loads(req.content)["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    p = OpenAICompat("ollama", "http://x/v1", "", "qwen-not-installed", needs_key=False, transport=httpx.MockTransport(h)); p.embed_model = "nomic-embed-text"
    assert p.available() and p.can_embed()
    p.chat([{"role": "user", "content": "x"}], 10, 5)
    assert seen["model"] == "gemma3:4b"  # regression: this used to pick the embedding model and fail with HTTP 400
