# Scalability strategy

**Position: build the measurements now, buy the infrastructure when a measurement demands it.** Nothing below is a benchmark of a production system; the load test ran one uvicorn worker, SQLite, on a developer machine.

## 1. Measured today (real, reproducible: `scripts/loadtest.py`)
Real DB: 27,316 problems, 7,769 submissions, 9,397 contests. Test user has 2,787 solved / 5,519 submissions (a heavy user). 8 concurrent clients, 64 requests/endpoint, 1 worker.

| Endpoint | Before: p50 / p95 (ms) | After: p50 / p95 (ms) | Service time @ concurrency 1 | Fix |
|---|---|---|---|---|
| `/explorer` (unfiltered) | 8,623 / 9,582 (0.9 rps) | **30 / 53** (165 rps) | 7 ms | SQL-side count/order/limit; solved via subquery |
| `/patterns/coverage` | 10,272 / 16,331 (0.7 rps) | **26 / 372** (92 rps) | 4 ms warm | only load touched problems; per-user cache keyed by evidence fingerprint + catalog version; single-flight lock |
| `/mastery` | 1,869 / 2,201 | **8 / 1,611** (p95 = cold stampede, no single-flight yet) | 68 ms uncached | bucketed MAP estimator; cached estimate |
| `/daily` (cached) | – | 9 / 15 (282 rps) | 2 ms | – |
| `/sheets` | – | 116 / 183 (57 rps) | 7 ms | **open**: N+1 count queries per sheet |
| `/contests`, `/patterns`, `/health` | – | 12 / 21, 14 / 32, 1 / 2 | – | – |

Reading: at concurrency 1 everything is ≤ 70 ms; the large loaded latencies were CPU saturation of one worker by an accidental O(catalog) request path (found only by measuring). The API is stateless → add workers.

## 2. Workload separation (target)
Interactive API (stateless, many) · platform sync + ingestion (queue workers, rate-limited per platform) · recommendation/analytics recompute (background, event-triggered, cache) · AI inference (separate pool, timeouts, token budgets, provider fallback) · RAG retrieval · code execution (isolated hosts) · realtime (WebSocket gateway + Redis pub/sub) · notifications. Sync and AI must never share a worker pool with interactive requests. Today: API + in-process worker thread only.

## 3. Capacity model — ASSUMPTIONS, not measurements
Assumptions (edit them, the arithmetic follows): DAU = 10% of registered; 150 API requests per active user-day; peak = 5× daily average; 30% of DAU sync once a day, ~50 new submissions each; 1,000 stored submissions per registered user; 20% of DAU use the mentor, 5 turns × 3k tokens; 10% of DAU run 10 code executions/day.

| Registered | DAU | Peak API rps | Submissions stored | Sync jobs/day | Mentor tokens/day | Code runs/day (peak/s ≈ ×5 avg) |
|---|---|---|---|---|---|---|
| 1,000 | 100 | ~1 | 1 M | 30 | 0.3 M | 100 (~0.006/s) |
| 10,000 | 1,000 | ~9 | 10 M | 300 | 3 M | 1,000 (~0.06/s) |
| 100,000 | 10,000 | ~87 | 100 M | 3,000 | 30 M | 10,000 (~0.6/s) |
| 1,000,000 | 100,000 | ~870 | 1 B (~200 GB at ~200 B/row) | 30,000 | 300 M | 100,000 (~6/s) |

What the measurements say about those rows: through 100k users the cached read paths fit a handful of workers; the first limits will be **DB write/IO for ingestion**, **cold recomputes**, and **LLM/sandbox capacity**, not simple reads.

## 4. Bottlenecks and planned responses
1. SQLite → PostgreSQL (needed for concurrency anyway); `submissions` hash/range partitioning by user/time at ~100M rows; keep `(user_id, submitted_at)` index.
2. JSON `LIKE` tag filter → normalised `problem_tags` table + index (before ~100k problems/tag-heavy queries).
3. Per-process caches → Redis (shared, with the same fingerprint keys); add single-flight to estimate cache.
4. `problem_patterns` rebuilds over the whole catalog (0.28 s cold per process) → precompute per catalog version, store in DB/Redis.
5. Sheets list N+1 → one grouped query.
6. Mastery rebuild replays all events per sync (O(history)) → incremental update per new event with periodic full rebuild.
7. External platform limits (CF 1 req/2 s): per-platform token buckets in Redis; spread syncs; backoff already implemented.

## 5. Reliability (implemented / planned)
Implemented: idempotent jobs, retry with exponential backoff, dead-letter state, timeouts, per-host rate limiting, checkpoints, graceful empty states. Planned: circuit breakers per platform, queue backpressure, multi-provider AI fallback, backups + restore drills, alerting.

## 6. Proposed SLOs (targets, not yet measured in production)
Read API p95 < 300 ms, p99 < 1 s · Daily Challenge generation p95 < 500 ms · sync job success ≥ 99% excluding source outages · job queue lag p95 < 60 s · error rate < 0.5%. Currently met on the dev machine for cached paths (see table); not validated under production-like conditions.

## 7. When to split services
Extract only on evidence: code execution (security isolation — day one), AI inference (cost/latency isolation), realtime gateway (connection-bound scaling). The rest stays a modular monolith until a module's load profile or team ownership demands otherwise.
