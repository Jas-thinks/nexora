# Implementation Roadmap

Status legend: ✅ done & tested · 🚧 in progress · ⬜ not started. Updated every milestone (this file is the resume-point across sessions).

| # | Milestone | Depends on | Exit criteria | Status |
|---|---|---|---|---|
| 1 | Audit + architecture docs | — | docs written | ✅ |
| 2 | Backend foundation: config, DB, models, migrations, auth (register/login/refresh/logout), authz, rate limit, audit, data export/delete | 1 | pytest green incl. failure/authz cases | ✅ 18 tests (auth, refresh-reuse, authz, rate limit, export/delete, BKT); Alembic migration verified; server boots |
| 3 | Platform adapter framework + Codeforces adapter (official API), sync checkpoints, idempotent ingest, manual-link fallback | 2 | adapter tests against recorded fixtures; live call needs network | ⬜ |
| 4 | Unified profile + analytics engine (+ metric definitions, freshness) | 3 | analytics tests on fixtures | ⬜ |
| 5 | Problem catalog + knowledge graph + BKT mastery + recommender + offline eval (Precision/Recall/NDCG@K, time-split, SYNTHETIC label) | 2,4 | reproducible eval script + report | 🚧 (BKT model + tests done; catalog, graph, ranker, eval not started) |
| 6 | RAG: ingest/chunk/embed/hybrid retrieve/rerank/cite + eval set; LLM abstraction; mentor orchestrator + hint ladder | 5 | retrieval eval report; validator tests | ⬜ |
| 7 | Frontend shell + design system + auth/onboarding/dashboard | 2 | runs, component tests | ⬜ |
| 8 | Monaco studio + sandbox execution worker + security tests | 2,7 | escape/limit tests pass in Docker | ⬜ |
| 9 | System Design Studio (React Flow + rule-based + LLM review) + interview sim | 6,7 | — | ⬜ |
| 10 | Contests (Codeforces API real; others where official) + reminders | 3 | — | ⬜ |
| 11 | Community + WebSocket chat + moderation | 2,7 | — | ⬜ |
| 12 | Gamification, Planner, Interview Arena, Digital Twin | 4,5,6 | — | ⬜ |
| 13 | E2E, perf, CI, Docker Compose, deployment docs | all | — | ⬜ |

## Prioritisation note
The "fully working integrated product" rule beats breadth. Vertical slice order: auth → Codeforces sync → mastery → recommendations → mentor chat → studio. Community, arena, and twin come last and may ship reduced.

## Known limitations (living list)
- No real-user data exists; all ML evaluation is synthetic until users arrive.
- Most platforms have no official API; see docs/architecture/ARCHITECTURE.md.
- LLM calls require an API key supplied by the owner (`LLM_API_KEY`).

## Status as of 2026-11-19 (replaces the earlier table; dependency order unchanged)
| Phase | Scope | Status |
|---|---|---|
| 0 Audit/architecture | docs | ✅ (PRODUCT_VISION, COMPLETE_FEATURE_INVENTORY, FEATURE_GAP_ANALYSIS, NEXORA_ARCHITECTURE, …) |
| 1 Intelligence foundation | taxonomy, ingestion, canonical problems, mastery, estimator | ✅ with limits (35/84 patterns unmeasurable) |
| 2 Core learning | explorer, daily challenge, recommender, revision | ✅ backend+UI; ❌ Monaco; ❌ mistake notebook; revision UI partial |
| 3 Visualization Studio | engine + 7 algorithms | 🚧 framework done; most of the catalogue not built |
| 4 AI mentor / RAG | — | ⬜ blocked on LLM key + Postgres/pgvector |
| 5 Advanced intelligence | knowledge tracing ✅ (BKT); digital twin, adaptive roadmap | 🚧 |
| 6 Ecosystem | contests ✅ (no reminders/prep); system design, interview arena, community, gamification | ⬜ |
| 7 Scale/reliability | load test + 3 hotspot fixes ✅; Postgres/Redis/Docker/CI/observability | 🚧 |

Why this order differs from the brief: the data/identity/measurement layer (phases 1, 2, 7-measure) had to exist before intelligence features could be real; the LLM-dependent phases were deferred because they need an API key and would otherwise be unverifiable mock-ups.

## Global problem acquisition (second directive) — status
Done: source probe of every seed, verified matrix, 7 working problem sources, resumable backfill/reconcile/details, quality + sync dashboard, catalog analytics, separate student-submission pipeline (unchanged), robots violation found and fixed (AtCoder history).
Not done: HTML parsers for Timus/UVa/USACO/Luogu etc. (rights unclear), Codeforces Gym problems, cross-platform alias detection, per-problem classification confidence + human-review workflow, scheduled periodic refresh, Redis-backed queue, statements/editorials (deliberately not stored).

## Third directive (student analytics, LLM, studio, community, labs, platform) — status
Done and verified: student analytics, LLM router + streaming + mentor + RAG + training capture, Monaco studio + sandbox, system design lab, community + WebSocket, gamification, scheduler, Docker/compose/CI, Postgres parity, 3D UI pass.
Defects found by verification and fixed: sandbox output-flood blocked `docker kill` (pipe not drained) · keyless Ollama always reported "configured" · stream reported the configured model instead of the one used · hint answers over-explained (added hard budgets) · local TTFT 87 s → 31 s by trimming the prompt · Postgres: GROUP BY on separately-parameterised expressions, SQLite-only JSON function, FK-violating test data.
Still open: embeddings/pgvector, Redis, hosted-provider verification (needs keys), Interview Arena beyond design, Mistake Notebook UI, observability, CI execution on GitHub, executor on a separate host.

## Next, in order (with acceptance criteria)
1. **Postgres parity + Docker Compose + CI** — all tests pass on Postgres; `docker compose up` yields a working stack. (M)
2. **Analytics dashboards** from ingested data — each chart has a definition + source tooltip; tests on aggregation. (M)
3. **Problem-level pattern labels** (reviewed) for the 35 unmeasured patterns — measured coverage ≥ 90% of non-category patterns on rated CF problems. (L)
4. **LLM abstraction + mentor with hint ladder** (needs `CODEMIND_LLM_API_KEY`) — answers cite trace frames/problem metadata; validator rejects uncited claims. (M)
5. **Monaco + sandbox** with escape tests. (L)

## Defects found by tests/measurement during this build (all fixed)
SQLite naive-datetime comparison made unchanged contests "updated" every sync · manual-import URLs never linked to canonical problems · DMOJ pagination fixture looped forever (added a hard page cap) · BFS highlighted a non-existent code line · rating estimator was non-monotonic (undamped Newton) and later credulous on success-only data · original max-type rating estimator inflated by lucky solves · "shaky prerequisite" shown for patterns that cannot be measured · cold-start daily challenge froze after the first sync · AtCoder rating history fetched from a robots-disallowed path (removed) · explorer O(catalog) (8.6 s → 30 ms) · pattern coverage recomputed per request (10 s → 26 ms) · migration used SQLite-incompatible ALTERs.

## Progress log
- 2026-11-19: M1–M2 foundation; catalog/sheets/recommender slice; platform registry + adapters + ingestion; sheet importers; canonical identity; pattern taxonomy + mastery; Daily Challenge; evaluation harness; Visualization Studio v1; contests UI; load testing and hotspot fixes; docs. Backend 141 / web 13 tests.

## Fourth directive ("build all this") — status, 2026-11-19
**Done and verified (tests + real runs):** holdout experiment with CIs that refuse claims below 30 users/arm · problem-level pattern labels (rule + LLM proposers, human review, proposer precision only after ≥20 reviews) · hybrid BM25+embedding retrieval (better on paraphrase, slightly worse on lexical queries — measured) · Mistake Notebook + Revision Centre · auto-verification of solves from synced submissions · contest prep/post-contest review + notifications (email only if SMTP) · learning planner with feasibility verdict · Mock Interview · Practice Arena (hidden tests validated in the real sandbox: reference solutions pass, naive O(n²) TLEs) · public profile (opt-in) · Java/JavaScript sandbox, compile-once judge · email verify/reset/MFA · Redis limiter · Prometheus/JSON logs · remote executor service · security headers · UI for all of the above (30 routes, build + 29 vitest pass, pages exercised in a real browser).
**Postgres parity:** all 329 backend tests pass on pgvector/pg16 after fixing two defects SQLite hid: `daily_challenges.policy_version` VARCHAR(20) overflowed on the control-arm label (would have crashed every control-arm user in production; migration `ffe90877a9d3`), and an FK-violating test fixture. `alembic check` reports no drift.
**Not done / not verified:** light theme, mobile pass and an axe accessibility audit · pattern learning pages · httpOnly-cookie tokens · full `docker compose up` end-to-end on this host (port 8000 is occupied here; needs an override) · load test on Postgres with the new features · executor on a separate host (unit-tested only) · GitHub Actions never executed · hosted LLM providers unverified (no keys) · Mock Interview/Arena UIs were smoke-tested for rendering, not exercised through a full multi-user flow in the browser · no real-user data, so the experiment and recommender quality claims remain unmeasured.

## X-factor features — status, 2026-11-19
**Stress tester (done, verified):** `POST /stress` + `/stress` page. Given a solution, a brute force and a Python generator (`<seed> <size>` on stdin) it compiles each once, runs hundreds of sandboxes, and reports the smallest failing input found (ascending sizes, then a shrink pass), the first diverging output line, RE/TLE as counterexamples, and distinguishes a broken generator/brute from a wrong solution. "No counterexample" is explicitly not a proof. Tested against real sandboxes (buggy solution found at small size; correct one not flagged) and in a real browser. Limits: local executor only (501 with a remote executor), 40 s budget, generator must be Python, no automatic input minimisation beyond the size schedule.
**Browser extension (built; live LeetCode format NOT verified):** `extension/` (MV3) + `POST /capture/submissions` with scoped `nxc_` tokens (hash-only storage, shown once, max 5, revocable, can only upload; cannot read anything). Captured rows get provenance `extension` ("captured, not verified"): they feed history/mastery but never auto-verify a Daily Challenge. Verified: 7 backend tests (+ Postgres), 5 parser tests, and a real-Chromium run in which the loaded extension captured fake-LeetCode responses (ignoring PENDING and `runcode_` polls) and uploaded to the real API (rows linked to the catalog problem; test rows then removed). **Not verified:** LeetCode's real response field names/URL (from memory of a private API), LeetCode's terms of service, behaviour in stable Chrome (I could only load it in Playwright's Chromium; stable Chrome ignores `--load-extension`), Chrome Web Store packaging/icons.
**Not started from the list:** virtual contests + post-contest timeline, proof-of-improvement page, shareable profile card, strategy coach, study groups, voice interview, PWA.

## Interview resources / design lab / crash course — status, 2026-11-19
Done and verified (details and limits in `docs/interview-resources.md`): company-wise resources (470 companies, 16,898 links ingested for real; tiers; must-do per tier; per-company filters and progress) · 70-question system-design library · open-ended Design Lab (any question, six HLD sections, inferred-needs rule check, AI "review and teach" mode with 24 first-party design notes, offline fallback) · 30/60-day DSA + system-design crash course with auto-completion, catch-up and streak · UI for all three, checked in a real browser; 364 backend tests (SQLite) and the new ones on Postgres.
Not done / caveats: the company-list source has **no licence** (owner must decide); company-specific *system-design* reports are not claimed (no verifiable open data); AI review quality only seen with a local 4B model; design notes not human-reviewed; LLD has no class-diagram canvas; crash-course effectiveness unmeasured.

## Distributed deployment, CI/CD and repository cleanup, 2026-11-19
Done and verified (details and numbers in `docs/architecture/distributed-system.md`): compose stack with nginx load balancer, 3 API + 2 web replicas, dedicated worker, one-shot migrations, isolated executor, Redis (shared rate limits, read cache, leader lease), Postgres, optional Prometheus + Grafana; atomic job claiming and stale-job reaper; leader election for the scheduler (Redis lease, Postgres advisory lock fallback); `/ready` vs `/health`; remote stress testing; failure drills (replica kill: 0/100 failed; Redis down: 0/73; Postgres restart: 5/175) and a smoke test (15 checks) run against the real stack. Bugs found by actually building and running it: `package-lock.json` out of sync (`npm ci` failed, so CI would have failed), the executor image had no Docker CLI on Debian 13, API replicas would each have run the scheduler and double-sent notifications, the Redis client never retried after a failed first connect, the rate limiter would have seen only the balancer's IP. CI (lint, SQLite + Postgres + Redis tests, web, extension, docs-sync, image build + scan, full-stack compose smoke), CD (GHCR images, SSH deploy with smoke test and rollback), CodeQL, dependency audit and Dependabot ran on GitHub for the first time on 2026-11-19: tests, web, extension, docs-sync and the full-stack compose job (smoke + failure drills) passed; the first run also exposed a non-existent action version (`trivy-action@0.28.0`) and CodeQL being unavailable on a private repo, both fixed. CD's publish/deploy and CodeQL have not run yet. Root docs moved under `docs/`.
Not done: redundancy of the data tier, load/soak testing, cloud-VM runs of `bootstrap.sh`/`deploy.sh`, TLS issuance, multi-arch builds, backups and a restore drill.
