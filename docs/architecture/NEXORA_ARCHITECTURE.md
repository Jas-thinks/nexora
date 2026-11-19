# Nexora architecture (current state + target)

See docs/architecture/ARCHITECTURE.md for the original modular-monolith rationale. This document records what is **actually implemented**.

## Runtime
```
Next.js 16 (React 19, TS) ──REST──▶ FastAPI app (1 process today; stateless, scale by adding workers)
                                     ├─ api/        auth · practice · integrations · learn (daily, patterns, revision)
                                     ├─ integrations/  registry · polite HTTP · adapters (CF, AtCoder, DMOJ, CodeChef, CLIST)
                                     ├─ importers/  neetcode · takeuforward · sheet-source registry
                                     ├─ services/   ingest (+job queue) · sheet_import · canonical · recommender · daily · quality
                                     ├─ patterns/   taxonomy · mapping · mastery (+caches)
                                     ├─ ml/ bkt     eval/ offline metrics & simulator
                                     └─ worker thread (polls sync_jobs)          ──▶ SQL DB (SQLite dev / Postgres target)
```
Not yet present: Redis, vector store, LLM gateway, code-execution workers, WebSocket gateway, object storage.

## Data flow (implemented)
1. User links a platform → adapter `validate_profile` hits the real platform (404 → 422, never "linked" blindly).
2. `POST /profiles/{id}/sync` enqueues a `SyncJob` (idempotent: one live job per target). Worker runs `sync_profile`: fetch since checkpoint → upsert `Submission` (unique user/platform/external_id) → upsert `RatingHistory` → refresh `ProblemStatus` (verified wins) → rebuild mastery (replay).
3. Daily Challenge: `build_ctx` (pattern states, outcomes, MAP rating, friction, due reviews) → pool (SQL window + sheet problems) → `rank` (six objectives) → explanation from the same feature values → persisted with weights/features.
4. Completion feedback → `ProblemStatus`, `ReviewItem` (Leitner), mastery rebuild, friction for the next pick.

## The brief's "binary search on answer" workflow — what exists
| Step | Status |
|---|---|
| 1 record outcomes | ✅ submissions + self-report |
| 2 mastery identifies weakness | ✅ pattern status `weak` — **only if the pattern is measurable** (`binary-search-answer` is, via the "on-answers" section of Striver's A2Z; CF tags cannot see it) |
| 3 knowledge graph checks prerequisites | ✅ `missing_prereqs` (unmeasured prereqs are excluded) |
| 4 mentor identifies concept gap | ❌ needs LLM |
| 5 visualiser teaches the monotonic predicate | ❌ no binary-search-on-answer visualisation yet (plain binary search exists) |
| 6 daily challenge recommends | ✅ |
| 7 solve in Monaco | ❌ (links out to the platform) |
| 8 evaluate result | ✅ self-report / next sync |
| 9 revision schedule | ✅ |
| 10 adaptation | ✅ friction + mastery rebuild |

## Key invariants (all tested)
- Re-syncing never changes mastery (deterministic replay). Unjudged submissions never advance a checkpoint. Unlinked submissions are kept and counted.
- Caches are keyed by evidence fingerprint + catalog version; they invalidate on new data.
