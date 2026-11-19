"""Evidence mapping: problem -> patterns, using platform tags and the sheet sections the problem appears in."""
from functools import lru_cache

from app.patterns.taxonomy import PATTERNS


# DMOJ's own tag vocabulary (observed in the live problem list) -> pattern. Matching is case-insensitive.
DMOJ_TAGS = {"dynamic programming": "dynamic-programming", "graph theory": "graph-traversal", "data structures": "advanced-ds",
             "greedy algorithms": "greedy", "simple math": "mathematics", "intermediate math": "mathematics", "advanced math": "number-theory",
             "geometry": "geometry", "string algorithms": "string-processing", "implementation": "implementation", "ad hoc": "implementation",
             "divide and conquer": "divide-and-conquer", "binary search": "binary-search", "brute force": "brute-force", "sorting": "sorting",
             "bitmasks": "bit-manipulation", "game theory": "game-theory", "combinatorics": "combinatorics", "number theory": "number-theory"}


@lru_cache
def _tag_index() -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for p in PATTERNS:
        for t in p.cf_tags:
            idx.setdefault(t.lower(), []).append(p.id)
    for t, pid in DMOJ_TAGS.items():
        if pid not in idx.setdefault(t, []):
            idx[t].append(pid)
    return idx


@lru_cache
def _section_rules() -> list[tuple[str, str]]:
    return [(s, p.id) for p in PATTERNS for s in p.sections]


def patterns_for(tags: list[str], sections: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Deterministic. Tags are exact-match; sections are substring-match on the sheet author's own section names."""
    out: list[str] = []
    for t in tags:
        out += _tag_index().get(t.lower(), [])
    for sec in sections:
        s = sec.lower()
        out += [pid for needle, pid in _section_rules() if needle in s]
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq


@lru_cache
def observable_patterns() -> frozenset[str]:
    """Patterns that CAN accumulate evidence today (some tag or sheet-section rule maps to them).
    Others are 'unmeasured': absence of evidence there says nothing about the student."""
    return frozenset({pid for ids in _tag_index().values() for pid in ids} | {pid for _, pid in _section_rules()})
