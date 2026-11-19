# Historical backfill report

_Generated 2026-11-19 13:43 UTC from the development database. Counts are `SELECT COUNT` results, not estimates._

| Item | Count |
|---|---:|
| Platform-specific problem records | 57,159 |
| Distinct canonical URLs | 57,159 |
| Contests | 9,401 |
| Sheets / sheet memberships | 9 / 1,327 |
| Records with ≥1 original platform tag (topic classifications) | 20,374 |
| Statistics snapshots | 44,543 |
| Historical submissions (2 public profiles used only for smoke testing; AtCoder rating history removed, see below) | 13,288 |
| Rating-history rows | 622 |
| Missing upstream / inaccessible records | 0 / 0 |
| Unresolved sync failures | 0 |
| Last completed enumeration | 2026-11-19 13:20:43.409467 |

| Platform | Discoverable (source's own count) | Retrieved | Enumeration | Last complete pass | Metadata completeness (title / difficulty / topics / contest / limits / stats) | Restrictions |
|---|---:|---:|---|---|---|---|
| Codeforces | 11526 | 11,526 | complete | 2026-11-18 23:58 UTC | 100.0% / 97.1% / 98.4% / 100.0% / 0.0% / 100.0% | rights Restricted; Official API (apiHelp). problemset.problems returned 11,526 problems incl. rating, tags, s… |
| AtCoder (via AtCoder Problems) | 9969 | 9,969 | complete | 2026-11-18 23:47 UTC | 100.0% / 49.3% / 0.0% / 100.0% / 0.0% / 99.4% | rights Unclear; kenkoooo merged-problems.json (9,969 problems, solver_count) + problem-models difficulty e… |
| CodeChef | 21697 | 21,597 | complete | 2026-11-18 23:51 UTC | 100.0% / 27.0% / 0.0% / 27.3% / 0.0% / 100.0% | rights Unclear; Public JSON /api/list/problems/all?limit&page reports count=21,697, paginated; difficulty_… |
| LeetCode | — | 3,407 | partial/none | — | – | rights Restricted |
| CSES | 400 | 400 | complete | 2026-11-18 23:58 UTC | 100.0% / 0.0% / 100.0% / 0.0% / 0.0% / 100.0% | rights Unclear; One public HTML page lists 400 tasks in sections with solved/attempted counts. No robots.t… |
| DMOJ | — | 5,274 | complete | 2026-11-19 13:20 UTC | 100.0% / 98.2% / 100.0% / 0.0% / 9.5% / 0.0% | rights Restricted; Public API v2: /problems (5,274 incl. types, points, group) and /problem/<code> (time/memo… |
| Project Euler | 1019 | 1,019 | complete | 2026-11-18 23:58 UTC | 100.0% / 0.0% / 0.0% / 0.0% / 0.0% / 100.0% | rights Restricted; minimal=problems plain-text list (ID, title, published, solved-by) returned 200. Content i… |
| yukicoder | 3967 | 3,967 | complete | 2026-11-18 23:58 UTC | 100.0% / 100.0% / 0.0% / 0.0% / 0.0% / 0.0% | rights Unclear; Official API /api/v1/problems returned 3,967 problems (No, Title, Level, Tags, Date). User… |

## How completeness is judged
"Discoverable" is the figure the source itself reports (CodeChef `count`, or the length of the listing it returned). A pass is `complete` only when pagination ended naturally; interrupted passes keep their checkpoint and resume. Records not seen by a later complete pass become `missing_upstream` (not deleted).
No platform is claimed 100% complete against an external ground truth: that cannot be verified, only "everything the source's listing returned".

## Failures
- none unresolved

## Corrections made during this work
- AtCoder rating history had been fetched from `atcoder.jp/users/*/history/json`, which `robots.txt` disallows. The fetch was removed, the capability marked unavailable, and the 37 previously stored rows were deleted.
