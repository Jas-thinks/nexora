# Technical Decisions

| Decision | Choice | Why | Rejected / trade-off |
|---|---|---|---|
| Topology | Modular monolith | One team, one deploy, transactional consistency; modules extractable | Microservices: operational cost with no measured need |
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic | Python is where the ML/RAG code lives; typed validation | Node backend would split the stack |
| DB | PostgreSQL (SQLite for dev/tests) | Relational core; pgvector for vectors | Dedicated vector DB (Qdrant): extra system until >~1M chunks or filtering/latency demands it |
| Vectors | pgvector + Postgres FTS (hybrid, RRF fusion) | Single store, metadata filters via SQL | FAISS only for offline experiments |
| Cache/queue | Redis | Rate limits, caching, pub/sub for WS fan-out, light jobs | Kafka: no throughput need |
| Jobs | Start with Redis-backed worker (arq/Celery) | Sync/ingest/embedding are I/O batch jobs | Celery if we need beats/canvas; decide at Phase 3 |
| Mastery model | Bayesian Knowledge Tracing per topic (+ forgetting decay) | Interpretable, works with tiny data, no cold-start training | Deep KT (DKT/SAKT): needs large interaction logs we do not have; revisit once real data exists |
| Recommender | Stage 1 candidate gen (content + knowledge graph + difficulty window) → Stage 2 LightGBM/logistic ranker trained on solve-outcome → Stage 3 rules/diversity + explanations | Honest, evaluable, explainable | Collaborative filtering only after enough users; bandits only with feedback volume |
| Rerank | Cross-encoder (small, local) behind interface | Measurable retrieval gain, to be ablated | Skipped if ablation shows no gain |
| LLM | Provider-abstracted (`LLMClient`), Anthropic default, fake client for tests | No lock-in, deterministic tests | — |
| Agents | **One orchestrator + deterministic tools**, not 8 chatting agents | Latency/cost; "agents" = workflow handlers with typed I/O | Multi-agent conversations rejected |
| Code exec | Separate worker, Docker (gVisor runtime if available), no net, RO rootfs, cgroups, pids limit | Untrusted code never in API process | Firecracker is stronger; documented upgrade path |
| Frontend | Next.js + TS + Tailwind, Monaco, Recharts/visx, React Flow | Standard, strong ecosystem | — |
| Auth | Self-hosted JWT access + rotating hashed refresh tokens | Full control, testable | Hosted IdP later if needed |
| Password hashing | scrypt (stdlib) now | No native deps; OWASP-acceptable params | argon2id preferred once dependency approved |
| Observability | structlog-style JSON logs, OpenTelemetry, Prometheus | Standard | Full Grafana stack only in Compose profile |

## Rules on results

No accuracy, latency, or user-count number appears in docs unless produced by a committed, reproducible script. Synthetic experiments are labelled `SYNTHETIC`.
