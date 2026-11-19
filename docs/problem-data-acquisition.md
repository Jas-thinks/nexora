# Problem data acquisition architecture

Global problem catalogue and student activity are **separate pipelines** sharing only the canonical `problems` table.

## Stages (code: `backend/app/sources/`)
1. **Discovery** – `ProblemSource.pages(cursor)` yields `(records, next_cursor)`; `discovered_total` is the source's own claim (e.g. CodeChef `count`).
2. **Fetch** – `PoliteClient`: per-host rate limit, retry with exponential backoff, `Retry-After`, hard page caps.
3. **Parse/normalise** – source-specific parsers produce `ProblemRecord` (identity, contest, difficulty *in the source's own scale*, tags, limits, stats, raw record).
4. **Persist** – `_upsert`: batch per page, idempotent on `(platform, external_id)`, never erases a field a richer stage filled, appends a `ProblemStatisticsSnapshot` only when counts change, stores `source`, `observed_at` and the **raw source record** separately from normalised columns.
5. **Checkpoint** – `SyncCheckpoint(platform, stage)` is committed in the same transaction as each page; interruption at any page boundary resumes from the cursor.
6. **Reconcile** – after a *complete* pass of a complete-enumeration source, records not observed become `missing_upstream` (never deleted); they return to `active` if they reappear.
7. **Details** – optional second stage (`run_details`), query-based resume, failures isolated per problem (`SyncFailure`), 404 ⇒ `inaccessible`.
8. **Validate/quality** – `services/catalog_stats` (completeness per field), `docs/problem-data-quality-report.md`.
9. **Analytics** – `/analytics/catalog` aggregates persisted rows in SQL; scales are never mixed.

## Execution
Backfills run as `SyncJob(kind="backfill")` on the worker (not in API requests); an interrupted run raises a retryable error so job backoff re-runs it and the checkpoint resumes. CLI: `scripts/run_backfill.py`. Admin API: `POST /admin/backfill/{platform}`; dashboard: `/sources`.

## Incremental sync
Single-call sources (Codeforces, AtCoder, yukicoder, Project Euler, CSES) are cheap to re-enumerate; a refresh pass upserts only differences (verified: second pass `updated=0`). Paginated sources (DMOJ, CodeChef) re-enumerate from page 1 with the same diff logic. No source offers a verified "changed since" cursor, so delta endpoints are not claimed.

## Rights model
`statement_access = link_only` for every source: statements, examples and editorials are not stored. Content-Signal `ai-train=no` sources are indexed for search/recommendation only. See global-problem-source-registry.md.

## Student activity (separate)
`ConnectedProfile` → `SyncJob(profile_sync)` → `Submission` (verified or user_imported) with per-profile checkpoints; history limits are returned per profile (`history_limitations`). Public solved counts are never turned into fake submissions.

## Known limits
No verified detail endpoint outside DMOJ (so limits/statement fields are mostly absent elsewhere); no problem↔contest link for DMOJ/CodeChef problems beyond CodeChef's `contest_code`; Codeforces Gym problems not ingested; cross-platform alias detection is not automated (aliases require explicit evidence).
