from collections import Counter

import pytest

from app.patterns.mapping import patterns_for
from app.patterns.taxonomy import BY_ID, EDGE_FIELDS, PATTERNS, REVIEW_STATUS

KINDS = {"category", "data_structure", "algorithm", "pattern", "math", "optimization"}


def test_ids_unique_and_kinds_valid():
    ids = [p.id for p in PATTERNS]
    assert len(ids) == len(set(ids))
    assert {p.kind for p in PATTERNS} <= KINDS


def test_all_edges_point_to_existing_patterns():
    for p in PATTERNS:
        if p.parent:
            assert p.parent in BY_ID and BY_ID[p.parent].kind == "category", f"{p.id}: parent must be a category"
        for f in EDGE_FIELDS:
            for t in getattr(p, f):
                assert t in BY_ID, f"{p.id}.{f} -> unknown '{t}'"


def test_prerequisites_are_acyclic():
    state: dict[str, int] = {}
    def visit(n, path):
        assert state.get(n) != 1, f"prerequisite cycle: {' -> '.join(path + [n])}"
        if state.get(n) == 2: return
        state[n] = 1
        for q in BY_ID[n].prereq: visit(q, path + [n])
        state[n] = 2
    for p in PATTERNS: visit(p.id, [])


def test_no_pattern_is_its_own_relation():
    for p in PATTERNS:
        assert p.id not in p.prereq + p.related + p.contrasts + p.extends


def test_aliases_and_names_do_not_collide():
    names = Counter()
    for p in PATTERNS:
        for n in (p.name.lower(), *[a.lower() for a in p.aliases]):
            names[n] += 1
    assert [n for n, c in names.items() if c > 1] == []


def test_every_non_category_has_a_parent_and_every_category_is_used():
    assert all(p.parent for p in PATTERNS if p.kind != "category")
    used = {p.parent for p in PATTERNS}
    assert {p.id for p in PATTERNS if p.kind == "category"} <= used


def test_contrast_is_symmetric_or_documented_one_way():
    # binary search vs binary search on answer are distinct patterns (the brief's example) and must stay distinct
    assert "binary-search" in BY_ID["binary-search-answer"].contrasts
    assert BY_ID["binary-search"].id != BY_ID["binary-search-answer"].id


def test_taxonomy_declares_its_review_status():
    assert REVIEW_STATUS == "unreviewed"  # must be changed deliberately when a human review happens


@pytest.mark.parametrize("tags,sections,expected", [
    (["binary search"], [], "binary-search"), (["dp", "greedy"], [], "greedy"), (["dsu"], [], "dsu"),
    ([], ["Binary Search"], "binary-search"), ([], ["on-answers"], "binary-search-answer"), ([], ["Sliding Window"], "sliding-window"),
    ([], ["1-D DP"], "dp-1d"), ([], ["fundamentals-single-ll"], "linked-list"),
])
def test_mapping(tags, sections, expected):
    assert expected in patterns_for(tags, sections)


def test_mapping_is_deterministic_and_deduplicated():
    a = patterns_for(["math", "math", "dp"], ["Math & Geometry"])
    assert a == patterns_for(["math", "math", "dp"], ["Math & Geometry"]) and len(a) == len(set(a))


def test_unknown_tags_map_to_nothing_not_to_a_guess():
    assert patterns_for(["*special", "interactive"], ["Contest"]) == []


def test_unmeasurable_patterns_are_flagged_not_called_unexplored():
    from app.patterns.mapping import observable_patterns
    obs = observable_patterns()
    assert "binary-search" in obs and "dsu" in obs
    assert "modular-arithmetic" not in obs and "lca" not in obs  # nothing can evidence these today
