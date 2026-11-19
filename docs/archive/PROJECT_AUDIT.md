# Project Audit

_Date: 2026-11-19_

## Findings

| Area | State |
|---|---|
| Repository contents | **Empty directory.** No files, no git history. |
| Frontend / Backend / DB / Infra | None exists |
| Auth, APIs, schemas | None exists |
| ML pipeline | None exists |
| Tests | None exist (nothing to run) |
| Entry points | None |
| Reusable components | None |

**Conclusion:** this is a greenfield build. Nothing is being replaced, and nothing is claimed to pre-exist.

## Local toolchain (verified)

- Node v25.2.0 / npm, Python 3.12.3, Docker 29.9.1 (daemon running), git.
- **Not installed locally:** PostgreSQL, Redis. They run via Docker Compose in deployment. Dev and tests use SQLite through SQLAlchemy so the suite runs anywhere; Postgres-specific features (pgvector, JSONB) are isolated behind the RAG/vector module and verified separately against the Compose Postgres.

## Consequences for the plan

1. No migration risk, but also no domain data. Problem catalog and knowledge corpus must be built by ingestion from legitimate sources (see ROADMAP).
2. Recommendation and RAG evaluation will initially run on **synthetic/simulated data and is labelled as such**. No real-user metrics exist.
