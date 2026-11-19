"""Problem-level pattern labelling. Two PROPOSERS (rules, LLM) feed a human review queue; only accepted labels count as evidence.
Why: platform tags are coarse, so 35 of 84 patterns could never be observed. Proposals use only metadata (title, tags, rating, platform):
no statements are stored or sent."""
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import ProblemPatternLabel
from app.models.catalog import Problem
from app.patterns.taxonomy import BY_ID, PATTERNS

AUTO_ACCEPT = 0.9  # only explicit-keyword rules (e.g. title says "Knapsack") may auto-accept; documented and reviewable

# (title regex, pattern, confidence, why)
TITLE_RULES = [
    (r"\bknapsack\b", "knapsack", .92, "title names the knapsack problem"), (r"\blongest (increasing|common) subsequence\b|\bedit distance\b|\bLIS\b|\bLCS\b", "dp-subsequence", .9, "title names a classic subsequence DP"),
    (r"\blowest common ancestor\b|\bLCA\b", "lca", .92, "title names LCA"), (r"\bsparse table\b", "sparse-table", .92, "title names sparse table"), (r"\bsegment tree\b", "segment-tree", .9, "title names segment tree"),
    (r"\bfenwick\b|\bbinary indexed\b|\bBIT\b", "fenwick", .9, "title names Fenwick/BIT"), (r"\btrie\b|\bprefix tree\b", "trie", .88, "title names a trie"),
    (r"\btopological\b", "topological-sort", .9, "title names topological sort"), (r"\bspanning tree\b|\bMST\b|\bkruskal\b|\bprim\b", "mst", .88, "title names a spanning tree algorithm"),
    (r"\bbridges?\b|\barticulation\b|\bstrongly connected\b|\bSCC\b", "bridges-scc", .85, "title names bridges/SCC"), (r"\bmerge sort\b|\binversions?\b", "merge-sort", .75, "title suggests merge sort / inversion counting"),
    (r"\bsieve\b|\bprime factor", "sieve", .85, "title suggests a sieve / factorisation"), (r"\bmodular inverse\b|\bmodulo inverse\b|\bfast exponent|\bpower mod\b|\bmodular exponent", "modular-arithmetic", .88, "title names modular inverse / fast power"),
    (r"\bdigit dp\b|\bdigit\b.*\bcount|\bnumbers? (with|having) digit", "digit-dp", .45, "title suggests digit counting"), (r"\bmonotonic\b|\bnext greater\b|\bhistogram\b", "monotonic-stack", .8, "title suggests monotonic stack"),
    (r"\bpermutations?\b|\bsubsets?\b|\bsubsequences\b|\bcombinations?\b", "subsets-permutations", .4, "title suggests enumeration"), (r"\bn-?queens?\b|\bsudoku\b", "backtracking", .9, "title names a backtracking classic"),
    (r"\bconvex hull\b", "convex-hull-trick", .5, "title mentions convex hull"), (r"\bdiameter\b", "tree-diameter", .7, "title mentions diameter"), (r"\bcentroid\b", "centroid-decomposition", .85, "title names centroid"),
    (r"\bheavy.light\b|\bHLD\b", "hld", .9, "title names HLD"), (r"\bbinary lifting\b|\bk-?th ancestor\b", "binary-lifting", .85, "title names binary lifting / k-th ancestor"),
    (r"\beuler(ian)? (path|circuit|tour)\b", "euler-tour", .85, "title names Eulerian path/tour"), (r"\bsweep\b|\bline sweep\b", "sweep-line", .7, "title suggests sweep line"),
    (r"\boffline\b|\bcoordinate compression\b", "offline-queries", .6, "title suggests offline queries"), (r"\bsqrt decomposition\b|\bMo'?s algorithm\b", "sqrt-decomposition", .9, "title names sqrt decomposition / Mo"),
    (r"\bsearch (in )?rotated\b|\brotated sorted\b|\bpeak element\b|\bbitonic\b", "rotated-search", .85, "title names rotated/bitonic search"), (r"\bfirst (bad|true|occurrence)\b|\blower bound\b|\bupper bound\b|\binsert position\b", "bounds", .75, "title suggests lower/upper bound"),
    (r"\bminimi[sz]e the maxim|\bmaximi[sz]e the minim|\bminimum .* maximum\b|\bcapacity to ship\b|\bsplit array largest sum\b|\bkoko\b", "binary-search-answer", .8, "title is a classic minimise-the-maximum"),
    (r"\bsort(ing)? (by|with) (custom|comparator)\b|\bcomparator\b|\blargest number\b", "custom-comparators", .7, "title suggests custom ordering"),
    (r"\binterval dp\b|\bburst balloons\b|\bmatrix chain\b|\bpalindrome partition", "interval-dp", .8, "title names an interval-DP classic"), (r"\brerooting\b|\bsum of distances in tree\b", "rerooting-dp", .85, "title names rerooting"),
    (r"\bz-?function\b|\bkmp\b|\bprefix function\b|\bpattern matching\b", "kmp", .85, "title names KMP/Z"), (r"\brolling hash\b|\brabin.karp\b", "string-hashing", .85, "title names rolling hash"),
    (r"\baho.corasick\b", "aho-corasick", .95, "title names Aho-Corasick"), (r"\bsuffix (array|automaton|tree)\b", "suffix-structures", .95, "title names suffix structure"),
]
# (required tag set, extra tag set (any), pattern, confidence, why)  -- combos of coarse tags that imply a finer pattern
COMBO_RULES = [
    ({"dp", "trees"}, None, "tree-dp", .65, "tags dp + trees"), ({"dp", "bitmasks"}, None, "bitmask-dp", .85, "tags dp + bitmasks"), ({"dp", "strings"}, None, "dp-subsequence", .4, "tags dp + strings"),
    ({"dfs and similar", "trees"}, None, "tree-traversal", .6, "tags dfs + trees"), ({"graphs", "shortest paths"}, None, "shortest-paths", .9, "tags graphs + shortest paths"),
    ({"number theory", "combinatorics"}, None, "modular-arithmetic", .4, "tags number theory + combinatorics (counting mod p)"), ({"number theory"}, {"math"}, "sieve", .3, "number theory tag (weak)"),
    ({"binary search", "greedy"}, None, "binary-search-answer", .5, "tags binary search + greedy (typical of answer search)"), ({"binary search", "two pointers"}, None, "bounds", .3, "tags binary search + two pointers"),
    ({"data structures", "trees"}, None, "segment-tree", .3, "tags data structures + trees (weak)"), ({"data structures", "divide and conquer"}, None, "segment-tree", .45, "tags data structures + D&C"),
    ({"dp", "math"}, None, "dp-1d", .3, "tags dp + math (weak)"), ({"dp", "graphs"}, None, "dp-2d", .25, "tags dp + graphs (weak)"),
    ({"strings", "hashing"}, None, "string-hashing", .55, "tags strings + hashing"), ({"geometry", "binary search"}, None, "convex-hull-trick", .2, "weak"),
]


def rule_proposals(p: Problem) -> list[tuple[str, float, str]]:
    out: dict[str, tuple[float, str]] = {}
    for rx, pat, conf, why in TITLE_RULES:
        if re.search(rx, p.name, re.I) and pat in BY_ID:
            out[pat] = max(out.get(pat, (0, "")), (conf, why))
    tags = {t.lower() for t in p.tags}
    for req, extra, pat, conf, why in COMBO_RULES:
        if req <= tags and (extra is None or tags & extra) and pat in BY_ID and conf > out.get(pat, (0, ""))[0]:
            out[pat] = (conf, why)
    return [(k, v[0], v[1]) for k, v in sorted(out.items(), key=lambda kv: -kv[1][0])]


def _upsert(db: Session, pid: int, pat: str, source: str, conf: float, reason: str) -> bool:
    ex = db.scalar(select(ProblemPatternLabel).where(ProblemPatternLabel.problem_id == pid, ProblemPatternLabel.pattern_id == pat))
    if ex is not None:
        return False  # never overwrite an existing label or a human decision
    status = "accepted" if source == "rule" and conf >= AUTO_ACCEPT else "proposed"
    db.add(ProblemPatternLabel(problem_id=pid, pattern_id=pat, source=source, confidence=conf, reason=reason[:300], status=status))
    return True


def propose_rules(db: Session, platform: str | None = None, limit: int | None = None) -> dict:
    q = select(Problem).where(Problem.status == "active")
    if platform:
        q = q.where(Problem.platform == platform)
    added = auto = n = 0
    for p in db.scalars(q.order_by(Problem.id)):
        n += 1
        for pat, conf, why in rule_proposals(p):
            if _upsert(db, p.id, pat, "rule", conf, why):
                added += 1; auto += conf >= AUTO_ACCEPT
        if limit and n >= limit:
            break
    db.commit()
    from app.patterns.mastery import bump_catalog
    bump_catalog()
    return {"problems_scanned": n, "proposals_added": added, "auto_accepted": auto}


PROMPT = """You label competitive-programming problems with algorithmic PATTERNS using ONLY the metadata given (no statement is available).
Choose 0-3 pattern ids from the list that this problem most likely trains. If unsure, return an empty list. Do not invent ids.
Return ONLY JSON: {{"patterns":[{{"id":"<id>","confidence":0.0-1.0,"reason":"<=15 words"}}]}}

Problem: {name} | platform: {platform} | rating: {rating} | tags: {tags}
Patterns (id: name): {catalog}"""
_CATALOG = "; ".join(f"{p.id}: {p.name}" for p in PATTERNS if p.kind != "category")


def parse_llm(text: str) -> list[tuple[str, float, str]]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0)).get("patterns", [])
    except (ValueError, AttributeError):
        return []
    out = []
    for x in arr[:3]:
        try:
            pid, conf = str(x["id"]), float(x.get("confidence", 0.5))
        except (KeyError, TypeError, ValueError):
            continue
        if pid in BY_ID and BY_ID[pid].kind != "category" and 0 <= conf <= 1:
            out.append((pid, conf, str(x.get("reason", ""))[:200]))
    return out


def llm_proposals(router, problem: Problem) -> list[tuple[str, float, str]]:
    msgs = [{"role": "user", "content": PROMPT.format(name=problem.name, platform=problem.platform, rating=problem.rating, tags=", ".join(problem.tags) or "none", catalog=_CATALOG)}]
    res = router.chat(None, None, msgs, purpose="label", max_tokens=200)
    return [] if res is None else parse_llm(res.text)


def propose_llm(db: Session, router, problem_ids: list[int]) -> dict:
    added = skipped = 0
    for pid in problem_ids:
        p = db.get(Problem, pid)
        if p is None:
            continue
        props = llm_proposals(router, p)
        if not props:
            skipped += 1
        for pat, conf, why in props:
            if conf >= 0.5 and _upsert(db, pid, pat, "llm", min(conf, 0.85), why):  # LLM confidence is capped: it never auto-accepts
                added += 1
    db.commit()
    return {"processed": len(problem_ids), "proposals_added": added, "no_proposal": skipped}


def accepted_map(db: Session) -> dict[int, list[str]]:
    m: dict[int, list[str]] = {}
    for pid, pat in db.execute(select(ProblemPatternLabel.problem_id, ProblemPatternLabel.pattern_id).where(ProblemPatternLabel.status == "accepted")):
        m.setdefault(pid, []).append(pat)
    return m
