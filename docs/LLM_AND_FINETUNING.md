# LLM integration, RAG and the fine-tuning path

## Providers (backend/app/llm)
One OpenAI-compatible client covers **Gemini** (`generativelanguage.googleapis.com/v1beta/openai`), **Groq**, **OpenRouter** and **Ollama**; **Anthropic** has its own client. Order and fallback are `CODEMIND_LLM_CHAIN` (default `gemini, groq, openrouter, ollama`). A provider with no key is skipped; a keyless local provider counts only if its `/models` endpoint answers. On a retryable failure (429/5xx/network) the router tries the next provider; every attempt is logged in `llm_calls` (provider, model, tokens, latency, ok/error).

| Provider | Env vars | Default model (configurable) | Verified |
|---|---|---|---|
| Google Gemini (free tier) | `CODEMIND_GEMINI_API_KEY` | `gemini-2.5-flash` | wire format by mock only (no key yet) |
| Groq (free tier) | `CODEMIND_GROQ_API_KEY` | `llama-3.3-70b-versatile` | wire format by mock only |
| OpenRouter (`:free` models) | `CODEMIND_OPENROUTER_API_KEY` | `meta-llama/llama-3.3-70b-instruct:free` | wire format by mock only |
| Ollama (local) | `CODEMIND_OLLAMA_BASE_URL` | auto-uses whichever model is installed | **live**: `gemma3:4b` on this machine |
| Anthropic | `CODEMIND_ANTHROPIC_API_KEY` | `claude-sonnet-5-5` | wire format by mock only |

"Free" and "best" are claims about third-party quotas and quality that change; **they were not verified**. Model names may need updating when you add keys. Recommended order when keys arrive: a hosted frontier-class free tier first for quality/latency (Gemini or Groq), OpenRouter as a spare, local Ollama as the private/offline fallback and the future home of the fine-tuned model.

## Mentor pipeline (services/mentor.py)
mode + hint level → **student context** (estimated rating, weak/strong patterns with evidence, deterministic) → **RAG** (BM25 + pattern-metadata boost over first-party notes, pattern cards, and *your* private notes; top 3, 800 chars each) → **one LLM call** (streamed) → **validators** → persist.
Validators (deterministic, tested): remove any URL not in the retrieved/problem allow-list; withhold code blocks >3 lines below hint level 5; trim to the per-level sentence budget (2/3/4/9 sentences for levels 1–4); retrieved/user text is wrapped as data and instruction-like lines are stripped. Daily token budget per user (default 60k / rolling 24 h). No provider → deterministic **offline mode** that answers only from notes and says so (levels 4–5 are not faked).

## RAG evaluation (tests/test_mentor.py, reproducible)
24 labelled student-style queries over 100 documents (14 first-party notes + 84 pattern cards), BM25 only: **Recall@3 = 0.958, MRR = 0.837**. The one miss is lexical: "check connectivity and merge components" retrieves merge-sort instead of DSU, a case embeddings should fix. Caveats: the query set is small and written by the same author as the notes; treat as a regression guard, not a benchmark. Embeddings/pgvector are not implemented yet (Postgres + pgvector image is in docker-compose, the vector column/index is not).

## Measured latency (local CPU only, `gemma3:4b`)
Time to first streamed token: 86.8 s with the original ~1.8k-token prompt, **31.5 s** after trimming to ~0.9k tokens; total ~38 s for a hint. CPU-only local inference is not interactive; hosted free tiers are expected to be much faster but are **unmeasured**. Streaming (SSE) is implemented so text appears as it is generated; the streamed text is an unvalidated draft that the validated final replaces.

## Fine-tuning later (what exists and what doesn't)
Exists: consent-gated capture. Students opt in (Settings or Mentor page, default off); only then is each non-offline answer stored in `training_examples` (mode, prompt, response, provider, optional thumbs rating) **without a user id**. `GET /admin/training/export?min_rating=0` returns JSONL in chat format.
Not done / honest plan: (1) collect enough examples (thousands; today there are none); (2) review/filter (thumbs, dedupe, remove personal data, check licences of base model); (3) LoRA/QLoRA on an open base (e.g. a Qwen2.5-Coder or Gemma class model) with a held-out eval: faithfulness to sources, hint-level discipline, no invented links, plus human review; (4) serve via Ollama and add it first in `CODEMIND_LLM_CHAIN`; (5) compare against the hosted baseline on the same eval before switching. A fine-tune is not guaranteed to beat a strong hosted model; measure first.
