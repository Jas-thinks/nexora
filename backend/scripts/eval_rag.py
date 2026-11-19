"""RAG retrieval evaluation: BM25 vs hybrid (BM25 + embeddings, RRF) on lexical AND paraphrased student queries.
Uses the real configured embedding provider (e.g. local Ollama nomic-embed-text). Prints Recall@3 / MRR for each set."""
import json, sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.db import Base
import app.models  # noqa
from app.llm.router import Router
from app.rag import service as rag
sys.path.insert(0, ".")
from tests.test_mentor import EVAL as LEXICAL

PARAPHRASE = [
    ("partition work among machines so the busiest one has the least", {"note:binary-search-answer", "pattern:binary-search-answer"}),
    ("group items that are connected and combine groups quickly", {"note:dsu", "pattern:dsu"}),
    ("walk a graph level by level to find the fewest edges", {"note:graph-traversal"}),
    ("cheapest route when every road has a positive cost", {"note:dijkstra", "pattern:shortest-paths"}),
    ("items have sizes and values and the bag has limited room", {"note:knapsack", "pattern:knapsack"}),
    ("count arrangements modulo a big prime with huge exponents", {"note:bit-modular", "pattern:modular-arithmetic"}),
    ("slide a frame across the array keeping a running total", {"note:sliding-window", "pattern:sliding-window"}),
    ("make the locally best choice every step and justify it", {"note:greedy", "pattern:greedy"}),
    ("answer lots of sum-over-a-range questions instantly", {"note:prefix-sums", "pattern:prefix-sums"}),
    ("for every element find the nearest bigger one on its right", {"note:monotonic-stack", "pattern:monotonic-stack"}),
    ("try every arrangement and undo the move when a branch fails", {"note:backtracking", "pattern:backtracking"}),
    ("change one element then ask about a stretch of the array", {"note:segment-fenwick", "pattern:segment-tree", "pattern:fenwick"}),
    ("two indexes closing in on each other in ordered data", {"note:two-pointers", "pattern:two-pointers"}),
    ("align two strings to find the longest shared order of letters", {"note:dp-lcs-lis", "pattern:dp-subsequence"}),
    ("break into overlapping smaller problems and remember answers", {"note:dp-foundations", "pattern:dynamic-programming"}),
    ("flip and test individual bits of a number", {"note:bit-modular", "pattern:bit-manipulation"}),
]


def evaluate(db, router, queries, k=3):
    hits = mrr = 0.0
    for q, ok in queries:
        keys = [h.key for h in rag.retrieve(db, q, k=5, router=router)]
        rank = next((i for i, x in enumerate(keys, 1) if x in ok), None)
        hits += rank is not None and rank <= k; mrr += 1 / rank if rank else 0
    return round(hits / len(queries), 3), round(mrr / len(queries), 3)


if __name__ == "__main__":
    eng = create_engine("sqlite:///:memory:"); Base.metadata.create_all(eng)
    with sessionmaker(bind=eng)() as db:
        rag.ingest_builtin(db); r = Router()
        emb = rag.embed_docs(db, r); print("embed docs:", emb)
        out = {}
        for name, qs in (("lexical(24)", LEXICAL), ("paraphrase(16)", PARAPHRASE), ("all(40)", LEXICAL + PARAPHRASE)):
            out[name] = {"bm25": evaluate(db, None, qs), "hybrid": evaluate(db, r, qs) if emb["embedded"] or emb["total"] else None}
        print(json.dumps(out, indent=1)); print("format: (Recall@3, MRR)")
