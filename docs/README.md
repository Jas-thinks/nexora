# Documentation index

**Start here:** [`../README.md`](../README.md) → [`architecture/distributed-system.md`](architecture/distributed-system.md) → [`DEPLOYMENT.md`](DEPLOYMENT.md)

| Area | Documents |
|---|---|
| **Architecture** | [distributed system](architecture/distributed-system.md) (what runs where, failure behaviour, what was verified) · [original modular-monolith rationale](architecture/ARCHITECTURE.md) · [as-built](architecture/NEXORA_ARCHITECTURE.md) · [technical decisions](architecture/TECHNICAL_DECISIONS.md) · [scalability strategy](architecture/SCALABILITY_STRATEGY.md) · [visualization studio](architecture/VISUALIZATION_STUDIO_SPEC.md) |
| **Operations** | [deployment runbook](DEPLOYMENT.md) · [security](SECURITY.md) · [code-execution sandbox](CODE_EXECUTION.md) · [testing](TESTING.md) |
| **Product** | [vision](product/PRODUCT_VISION.md) · [feature inventory](product/COMPLETE_FEATURE_INVENTORY.md) · [gap analysis](product/FEATURE_GAP_ANALYSIS.md) · [daily challenge engine](product/DAILY_CHALLENGE_ENGINE.md) · [pattern taxonomy](product/DSA_CP_PATTERN_TAXONOMY.md) · [roadmap and honest status](ROADMAP.md) |
| **Learning engine** | [recommendation engine](recommendation-engine.md) · [analytics and metrics](analytics-metrics.md) · [LLM and fine-tuning](LLM_AND_FINETUNING.md) · [pattern coverage](pattern-coverage.md) |
| **Data platform** | [data ingestion](data-ingestion-architecture.md) · [problem data model](problem-data-model.md) · [source registry](global-problem-source-registry.md) · [acquisition](problem-data-acquisition.md) · [platform integrations](platform-integrations.md) · [capability matrix](platform-capability-matrix.md) · [contest intelligence](contest-intelligence.md) |
| **Interview resources** | [company lists, design library, provenance and licence risk](interview-resources.md) |
| **Generated** (do not edit by hand) | [API reference](API.md) · [data-quality report](problem-data-quality-report.md) · [backfill report](historical-backfill-report.md) · [sheet registry](sheet-import-registry.md) |
| **Archive** | [initial project audit](archive/PROJECT_AUDIT.md) (historical; describes the empty starting point) |

Generated documents come from `make docs` (`backend/scripts/gen_docs.py`). Data-dependent reports reflect the database they were generated against.
