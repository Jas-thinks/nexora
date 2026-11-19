# Complete feature inventory

Verified on 2026-11-19. **Done** = works end to end and has tests. Tests: backend 242 (pytest; the same 242 pass on SQLite and Postgres 16), web 13 (vitest). Where a feature was also run against live networks, that is noted.

## Done
| Area | Feature | Evidence |
|---|---|---|
| Identity | Register/login, scrypt hashing, JWT access + rotating refresh with reuse detection, roles, rate limit, audit log, data export, account deletion | tests/test_auth.py |
| Integrations | Registry of 39 platforms with status/evidence/limitations; honest capability matrix | tests, docs/platform-capability-matrix.md |
| Integrations | Adapters: Codeforces (profile, submissions, rating history, contests, problems), AtCoder (same via community API + public history JSON), DMOJ (contests, problems), CodeChef (contests only), CLIST (needs user key; **not verified live**) | fixtures from real responses; live sync run |
| Ingestion | Polite HTTP (rate limit, retry, Retry-After), incremental checkpoints, idempotent upserts, DB-backed job queue with backoff + dead-letter, in-process worker | tests; live: 5,519 CF submissions synced via worker |
| Ingestion | Manual CSV/JSON import (USER_IMPORTED) with per-row rejection report | tests/test_integrations_api.py |
| Sheets | Importers: NeetCode (MIT repo data, 3 sheets), takeUforward (A2Z, SDE, 79, 75, 180, Blind 75), user import by IDs/URLs; order/sections/provenance preserved; canonical dedupe | docs/sheet-import-registry.md; live import: 9 sheets, 0 invalid URLs |
| Data model | Canonical problem identity (platform+external id from verified URL patterns); one problem, many sheet memberships | tests/test_sheets.py |
| Intelligence | BKT mastery with forgetting + difficulty adjustment; MAP rating estimator (failures-aware, guard-railed) | tests/test_bkt.py, test_rating_estimator.py |
| Intelligence | Pattern taxonomy v0.1 (98 nodes), evidence mapping, multi-signal pattern mastery with explanations, `unmeasured` status | tests/test_patterns.py, test_daily.py |
| Daily Challenge | Personalised multi-objective ranker, explanations from real features, cold start (refreshes after sync), modes (personalised/CP/interview/revision/topic), difficulty paths, one swap, feedback loop (friction), Leitner revision schedule, history | tests/test_daily.py; UI page |
| Evaluation | Metrics (P/R/NDCG@K), no-leakage `as_of` evaluation, baselines + ablation, REAL temporal split, SYNTHETIC simulator | tests/test_eval.py; docs/recommendation-engine.md |
| Visualizer | 8 algorithms with real traces (binary search, quick sort, BFS, LCS, Dijkstra, knapsack, sliding window), step back/forward, speed, custom input with validation, invariants, code-line sync | web/lib/viz.test.ts (13) incl. brute-force/Bellman-Ford cross-checks |
| Contests | Calendar from real sources (CF, AtCoder, DMOJ, CodeChef), timezone display, countdown, .ics export, last-synced | live data in UI |
| UI | Landing (3D), auth, shell with grouped nav, Overview, Practice, Explorer, Sheets, Patterns, Daily, Platforms, Contests, Visualizer | Playwright screenshots on real data |
| Quality | Data-quality report, load test script with before/after numbers | docs/data-quality-report.md, docs/SCALABILITY (below) |

| Global problem acquisition | Checkpointed, resumable, idempotent backfill engine; source adapters for Codeforces, AtCoder, DMOJ (+details), CodeChef (21,697, paginated), yukicoder, Project Euler, CSES; reconciliation (`missing_upstream`), statistics snapshots, per-problem provenance + raw record, failures table, `backfill` job kind | tests/test_sources.py (interrupt/resume, retry, reconcile, idempotency); live runs, docs/historical-backfill-report.md |
| Source matrix | 42 sources probed (status, robots, Content-Signal, JSON endpoints) → capability matrix with evidence; test fails if a seed source is omitted or a robots-disallowed API is marked usable | docs/platform-capability-matrix.md, docs/evidence/ |
| Catalog APIs/UI | `/sources`, `/problems/{id}` (provenance, contest, stats history), `/analytics/catalog`, `/admin/backfill/{platform}`; Data Sources dashboard, problem detail page | tests/test_catalog_api.py; screenshots |

| Student analytics | `/analytics/me` + page: heatmap, weekly acceptance, difficulty trend, rating history, verdicts/languages/tiers, topics strongest/weakest/improving/stagnating, abandoned/repeated failures, next best action, definitions + freshness | tests/test_student_analytics.py (11); live on a real synced profile |
| LLM layer | provider router (Gemini, Groq, OpenRouter, Ollama, Anthropic) with fallback, usage log, token budget, SSE streaming | tests/test_mentor.py (26); **live** against local Ollama `gemma3:4b`; hosted providers by mock only |
| AI mentor + RAG | modes incl. hint ladder (budgeted), grounded prompts, validators (URL allow-list, code withholding, hint budget), offline mode, private notes, consent-gated training capture/export; BM25 RAG over 100 docs (Recall@3 0.958, MRR 0.837, n=24) | tests; browser E2E |
| Coding studio | Monaco (custom theme), C++17/Python, run + sample-test judge, drafts autosave, run history, AI actions on code | browser E2E (Python run → 55) |
| Sandbox | Docker isolation, bounded I/O, rate limit + concurrency cap, graceful 503 | tests/test_sandbox_security.py (13 adversarial, real containers) |
| System design lab | React Flow editor, 6 scenarios, deterministic reviewer (SPOF, exposed datastore, cache/queue/media/consistency, auth, rate limit, observability), interviewer follow-ups, AI interviewer, save/load | tests/test_design.py (9); browser E2E |
| Community | 12 default channels, threads, reactions, code snippets, bookmarks, follows, search, pagination, reports, mutes, roles, spam controls, WebSocket live feed | tests/test_community.py (6); browser E2E (live post) |
| Gamification | XP (once per problem; unverified = 50%), levels, streaks, 11 evidence-backed badges, daily/weekly goals, personalised weekly challenge (redirects to a weak prerequisite), opt-in leaderboard | tests/test_gamification.py (11) |
| 3D / motion | pattern galaxy (R3F), XP orb, tilt cards, confetti on level-up/badge/daily completion, animated progress rings | browser screenshots |
| Scheduler | stale profile syncs (oldest first, bounded), contest and weekly catalogue refresh | tests/test_scheduler.py |
| Platform | Dockerfiles, docker-compose (pgvector/pg16), CI workflow, Postgres parity | image built + smoke-tested on Postgres; CI not yet run on GitHub |

## Partially done
- **Revision**: scheduling + due queue exist (API + panel on Daily page); no dedicated Revision Centre.
- **Hints**: pattern-level hints (levels 1–2) from the taxonomy only; problem-specific hints/explanations need the AI mentor.
- **Analytics**: Overview shows rating estimate, topic radar and focus areas; no time-series dashboards (rating history, activity, consistency) yet even though the data is ingested.
- **Pattern Universe**: taxonomy + relationships + mastery + real problems per pattern; learning pages are **outlines** (no written intuition/templates/mistakes); only 49 of 84 patterns are measurable.

## Not built
Embeddings/pgvector retrieval · Redis · Interview Arena (mock interviews beyond the design interviewer) · Mistake Notebook UI · Digital Twin · Autonomous planner (the weekly challenge is a first step) · Developer profile page · push notifications/reminders · light theme · observability (OTel/Prometheus) · more languages in the sandbox · 1v1 Practice Arena · 34 platforms beyond link-only · LeetCode/CSES/Love Babbar/Grind75 sheets · CP-31 and Striver CP (not importable, see registry).
