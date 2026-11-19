# Problem & learning data model

```
users 1─* connected_profiles 1─* submissions *─1 problems *─* sheets (via sheet_items; sheet_sections order the hierarchy)
users 1─* problem_status (progress: solved, attempts, provenance, first_solved_at)
users 1─* topic_mastery (BKT per tag) | rating_history | daily_challenges | review_items | sync_jobs
contests (platform, external_id) | problem_aliases (explicit equivalences) | data_quality_reports | audit_log | refresh_tokens
```
## Canonical identity
`problems(platform, external_id)` is unique. `services/canonical.canonicalize(url)` derives `(platform, external_id, canonical_url)` from verified URL patterns (CF, LeetCode, AtCoder, CSES, GfG, SPOJ, Kattis, DMOJ, CodeChef, HackerRank, Project Euler, Timus). **Titles are never used to merge.** A problem on many sheets = one row + many `sheet_items`. Cross-platform equivalence is only recorded explicitly in `problem_aliases` with evidence (currently unused: no verified mirrors).

## Provenance fields
`submissions.provenance` (verified | user_imported), `problem_status.provenance` (self_reported | verified_submission | user_import; verified wins), `sheets.source_url/license/imported_at/content_hash/import_report`, `problems.source_difficulty` (label as given by the first source), `contests.source` + `synced_at`.

## Entities from the brief not modelled separately
Platform (code registry, not a table), Topic/Algorithm/ProblemTopic (tags JSON + code taxonomy; a normalised `problem_tags` table is planned), ContestParticipation (rating rows only; unrated participation not stored), Recommendation/RecommendationFeedback (= `daily_challenges.feedback`), StudySession, UserGoal, LearningEvent, DataSource (= `contests.source`).
