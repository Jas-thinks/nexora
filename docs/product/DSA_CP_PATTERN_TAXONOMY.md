# DSA / CP pattern taxonomy

Source of truth: `backend/app/patterns/taxonomy.py` (v0.1.0, **authored by engineering, review_status = unreviewed**). Measured coverage: docs/pattern-coverage.md.

## Model
- `kind` distinguishes concepts that are related but not interchangeable: **category**, **data_structure**, **algorithm**, **pattern** (problem-solving idea), **math** (mathematical technique), **optimization**, e.g. *Binary search* (algorithm) vs *Binary search on answer* (pattern) vs *Parallel binary search* (optimization).
- Edges: `prereq`, `related`, `contrasts` (similar but distinct, never merge), `extends`. Each non-category has a parent category.
- Evidence rules: platform tags (exact, case-insensitive; CF + DMOJ vocabularies) and sheet-section substrings (the sheet author's own labels).

## Validated in tests
Unique ids/aliases; every edge target exists; prerequisites acyclic; parents are categories; every category is used; no self-relations; mapping deterministic, deduplicated, and returns nothing (not a guess) for unknown tags.

## Known limitations (read these)
1. **Measurability**: 35 of 84 patterns have no evidence rule (e.g. tree-dp, knapsack, lca, modular-arithmetic). They display `unmeasured`, are excluded from prerequisite gaps, and cannot be recommended on evidence. Fix = problem-level labels (gap #1).
2. Relationships are my judgement (e.g. `tree-dp` prereq `tree-traversal`), not yet reviewed against editorials or CP references.
3. Learning pages are outlines (metadata, relationships, real problems by tier). Intuition/templates/mistakes are not written.
4. Taxonomy is not exhaustive (the brief lists 36 top-level categories; ~14 categories / 84 patterns are modelled).

## Maintenance process (designed, partially implemented)
Version string + review status are exposed by `GET /patterns`. Changes: add/merge/deprecate via PR with the validity tests; aliases prevent duplicate patterns across sources; any human review flips `review_status` deliberately (a test pins it to `unreviewed` until then).
