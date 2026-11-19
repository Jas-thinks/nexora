# Feature gap analysis

Effort: S ≈ 1–2 days, M ≈ 1 week, L ≈ 2–4 weeks, one engineer, including tests. Estimates are judgement, not measurements.

| # | Gap | Why it matters | Depends on | Effort | Risk |
|---|---|---|---|---|---|
| 1 | **Problem-level pattern labels** (human-reviewed) for fine patterns (tree DP, knapsack, LCA…) | 35 of 84 patterns are unmeasurable; mastery/daily cannot reason about them | taxonomy review process | L (labelling is the cost) | needs human reviewers; LLM-assisted labelling must be validated against reviewed ground truth |
| 2 | LLM provider abstraction + AI mentor with hint ladder, grounded in trace/problem metadata | hints 3–5, post-solve explanation, visualiser Q&A all need it | API key from owner | M | hallucination → needs citation/validation layer |
| 3 | RAG (pgvector, hybrid retrieval, eval set) for patterns/editorial links | grounds the mentor; also powers pattern pages | #2, Postgres | L | corpus licensing; only metadata/links for third-party content |
| 4 | Monaco workspace + sandbox runner (Docker/gVisor, no network, cgroups) | closes the solve loop inside Nexora (Daily currently links out) | Docker host | L | sandbox security is the hard part; needs escape tests |
| 5 | Analytics dashboards (rating history, activity heatmap, consistency, difficulty trend) | data is already ingested; high perceived value | none | M | low |
| 6 | Revision Centre + Mistake Notebook UI | revision engine exists; mistakes need verdict/tag analysis | none | M | low |
| 7 | Production platform: Postgres+Alembic parity run, Redis, Docker Compose, CI | everything so far ran on SQLite | none | M | JSON-tag filter must move to a normalised table |
| 8 | Observability + SLOs | no production telemetry yet | #7 | S–M | low |
| 9 | Gamification (XP/streak/badges), study groups | engagement; must reflect real progress | #5 | M | gaming/leaderboard fairness |
| 10 | System Design Lab, Interview Arena | differentiators | #2 | L each | LLM quality |
| 11 | Community / real-time chat | engagement | #7 | L | moderation burden |
| 12 | More platforms (verify APIs: Kattis, CSES, Toph, Eolymp, yukicoder, …) | breadth | none | S per platform investigation | ToS/robots constraints |

## Challenges to the brief
- **36 top-level categories, 20-section pattern pages for each**: writing these before there is review capacity produces confident-looking text nobody has verified. Nexora ships structure + relationships + real problems first, and writes content for a pattern only when it can be reviewed.
- **Million-user readiness before 1,000 users**: build the measurement (load tests, SLOs) now; defer the infrastructure (see docs/architecture/SCALABILITY_STRATEGY.md).
- **"Mastery from solved count" is rejected**: it is gameable and wrong; mastery here combines four signals and is explained.
