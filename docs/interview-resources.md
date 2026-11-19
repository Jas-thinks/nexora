# Interview resources, open-ended System Design Lab, crash courses

## Data sources and what they mean
| Data | Source | Trust |
|---|---|---|
| Company → problem lists (DSA) | Community-reported lists in the public GitHub repo `liquidslr/leetcode-company-wise-problems`, fetched by `scripts/ingest_company_lists.py` | **Unofficial.** Candidates' recollections aggregated by a third party; can be stale or wrong; says nothing about what *you* will be asked |
| Company tiers (FAANG, Big tech, Product, Finance, Service, Other) | Nexora's own grouping in `app/resources/tiers.py` | **Editorial, not salary data.** "Service-based" = large IT-services/mass recruiters whose entry offers are commonly below ~10 LPA; pay varies by role, college and year |
| Difficulty, topics | The same lists (LeetCode's labels) | As reported |
| System-design questions (70: 60 HLD + 10 LLD) | Written for Nexora (`app/resources/design_questions.py`) | `level` is our judgement of typical seniority. **No company-specific system-design reports are claimed**: no open dataset of them exists that I could verify |
| Company → design relevance | Editorial `domain` (e-commerce, payments, …) | A practice hint, labelled as such in the UI |
| Teaching notes the mentor uses for design | 24 first-party notes (`app/rag/design_notes.py`) | Authored, **not yet human-reviewed** |

## Licence risk (decision for the owner)
The company-list repository **declares no licence** (all rights reserved by default). Nexora therefore never commits its files, fetches them at run time on an admin's command, stores only facts (company, problem link, title, difficulty, topics, reported frequency, recency), never stores problem statements, and attributes the source in the UI. Whether that is acceptable for a public product is the owner's call; to remove the data: `DELETE FROM companies WHERE source = 'github:liquidslr/leetcode-company-wise-problems'` (cascades). Problems created by the ingest have `source = 'github:liquidslr/leetcode-company-wise-problems'`.

## Ingest (measured on 2026-11-19)
`CODEMIND_DATABASE_URL=... PYTHONPATH=. python scripts/ingest_company_lists.py [--only Amazon TCS]`: 470 companies, 16,898 company↔problem links, 3,396 distinct problems (2,860 newly created), 0 failures, ~25 min (polite 0.15 s delay, 2 files/company: all-time and last-6-months). Idempotent per company. Adding a source = a parser returning `[{slug,url,name,difficulty,frequency,topics}]` plus `store_company`.

## API
`GET /resources/overview` · `/resources/companies?tier&q&limit&offset` · `/resources/companies/{slug}` · `/resources/companies/{slug}/problems?difficulty&topic&recent&unsolved&sort&limit&offset` · `/resources/must-do?tier&difficulty&unsolved` (problems asked by the most companies in a tier) · `/resources/system-design?level&category&kind&domain&q`. All paginated/filtered in SQL; per-user solved state comes from `ProblemStatus`.

## System Design Lab (open-ended)
Any question: free text or a library pick (`/design?question=<slug>`). The student writes six HLD sections (requirements, estimation, API, data model, deep dives, trade-offs), draws the diagram, then:
* **Rule check** (deterministic): SPOFs, exposed datastores, missing cache/queue/search/object storage, consistency mismatch, auth/rate-limit/observability. With no template it **infers needs from the prompt's words** (shown to the student, so they can disagree).
* **AI review** (`mode=design_review`): sees the question, notes, diagram and rule findings (all as data, with injection stripping) and replies with: what was done well, ranked gaps, a *Teach me* section grounded in the first-party notes, interviewer follow-ups, estimated scores. Findings are explicitly the checker's, not the student's claims (a first local-model run wrongly praised the student for them; fixed in the prompt).
* **No LLM configured**: an offline review from the rules and notes, labelled as unable to judge reasoning.
Limits: AI output can be wrong; local 4B models are weaker than hosted ones (not compared here); LLD questions use the same written sections but have no class-diagram canvas.

## 30/60-day crash course
`POST /planner/crash-course {days: 30|60, track: both|dsa|sd, level, target: tier|company, hours}`. Deterministic, no LLM: DSA topics get time by weight (halved if the student already solved ≥70% of that topic), problems are the most-reported unsolved ones for the target ranked by number of companies then frequency, shaped to the level's difficulty mix with an easy→hard ramp; system-design days = concepts first, then library questions (diverse categories, boosted by the company's domain); a mock + review day every 7th day and at the end; final days mixed practice + revision. Problem tasks auto-complete when synced submissions show a solve. **It is a schedule, not a prediction**; no evidence yet that it improves outcomes (no users to measure).

## Verified vs not
Verified: parsers, idempotent store, API filters/pagination/progress (SQLite + Postgres), plan structure invariants (no duplicate problems, mock cadence, skips solved), design persistence/ownership, prompt contents and injection handling, offline review, real ingest, real-browser run of resources, design lab (incl. a real local-LLM review) and planner.
Not verified: quality of AI reviews with hosted models; correctness of community-reported company lists; any claim about pay; behaviour of the ingest if the source repo changes its layout (the run reports per-company failures instead of stopping).
