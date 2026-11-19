# Architecture (CodeMind AI)

> Original design rationale (modular monolith + isolated execution workers). For how the system is actually deployed and what breaks when each part fails, see [distributed-system.md](distributed-system.md).

## Style: modular monolith + isolated execution workers

One FastAPI deployable, internally split into modules with explicit service interfaces (no cross-module table access). Only code execution runs outside the monolith, because it is untrusted.

```
 Next.js (React/TS) ──REST/WS──▶ FastAPI modular monolith ──▶ PostgreSQL (+pgvector)
                                  │  identity  profiles  integrations   Redis (cache, rate-limit,
                                  │  catalog   analytics recommender     pub/sub, job queue)
                                  │  mentor(orchestrator) knowledge(RAG)
                                  │  contests  community notifications  Object storage (S3/MinIO)
                                  ▼
                           Job queue (Redis) ──▶ Workers: sync, ingest, embed, aggregate
                                  ▼
                           Execution workers (separate hosts/containers: gVisor/Docker,
                           no network, read-only FS, cgroup CPU/mem/pids, wall-clock kill)
```

## Modules (`backend/app/modules/*`)

identity · profiles · integrations (PlatformAdapter) · catalog · analytics · recommender · knowledge (RAG) · mentor (orchestrator) · execution · contests · community · gamification · notifications.

Rule: modules talk via service functions / events, so any can be extracted later.

## Core data flow

1. Adapter pulls platform data incrementally (checkpoint per account) → raw payload stored → normalised to `Submission`/`Contest`/`Rating` (idempotent upsert on `(platform, external_id)`), each field tagged `verified | estimated | unavailable`.
2. Ingestion emits `SubmissionIngested` → mastery updater (BKT) updates `TopicMastery` → analytics aggregates refresh.
3. Recommender reads mastery + knowledge graph + candidate problems → ranked list with machine-generated reasons.
4. Mentor orchestrator: classify intent → load student context (deterministic) → retrieve knowledge (hybrid) → single LLM call with structured output → validator checks citations/hint-level → respond.

## Honest constraints on integrations

| Platform | Legit source | Notes |
|---|---|---|
| Codeforces | Official public API | Profile, submissions, contests, ratings |
| AtCoder | No official API; community-maintained read-only datasets (kenkoooo) | Mark as `third-party` |
| CodeChef, LeetCode, GfG, HackerRank, HackerEarth, SPOJ, TopCoder | No stable official public API for user history | Manual link + user-supplied export/import; contests from official calendars where exist. Never scraping behind auth or anti-bot |
| CSES | No API | Manual progress import |

An adapter declares its `capabilities`; the UI shows exactly what is verified vs unavailable.

## Security posture

Scrypt/argon password hashing, short-lived JWT access + rotating refresh tokens (hashed in DB), per-IP/user rate limiting, audit log, GDPR-style export/delete, secrets only from env, untrusted-content handling in the LLM prompt (retrieved text is data, never instructions).
