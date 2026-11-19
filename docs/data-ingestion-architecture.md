# Data ingestion architecture

`ConnectedProfile` → `SyncJob` (queued/running/succeeded/failed/dead) → worker → adapter → normalise → idempotent upsert.

- **Idempotent**: unique keys (`user,platform,external_id`; `platform,external_id`); enqueue returns the existing live job; re-sync reports `added: 0`.
- **Incremental**: per-profile `checkpoint` (CF `last_id`, AtCoder `last_epoch`). A still-judging CF submission holds the checkpoint back so it is never skipped.
- **Retries**: network/429/5xx are retryable (honours `Retry-After`; 3 attempts with exponential job backoff 30 s·2^n); 4xx and `NotSupported` are permanent. Exhausted retries → `dead` (the dead-letter state, visible in the UI and the data-quality report).
- **Rate limiting**: per-host minimum interval inside `PoliteClient` (CF 2 s). Pagination loops are capped (DMOJ 200 pages).
- **Validation**: manual import validates verdict, ISO timestamp, no future dates, platform-matching URLs; rejected rows are returned, not dropped.
- **Worker**: an in-process thread polls every 3 s (`CODEMIND_WORKER_ENABLED`). Verified end to end: a real CF profile (5,519 submissions) synced in 18 s through the queue. At scale: dedicated worker processes + Redis queue; same job semantics.
- **Monitoring**: `sync_jobs` table, `GET /sync-jobs`, `GET /admin/data-quality`.
- **Not done**: scheduled periodic re-sync, per-platform circuit breakers, Redis queue, dead-letter replay UI.
