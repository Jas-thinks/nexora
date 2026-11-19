# Contributing

## Set up
```bash
make install      # backend venv (+ dev tools) and web deps
make dev-api      # :18080, SQLite
make dev-web      # :3000
```

## Before you open a PR
```bash
make lint         # ruff (correctness rules) + tsc
make test         # backend on SQLite, web (vitest), extension (node --test)
make test-pg      # backend on Postgres + Redis, needs Docker; CI runs this too
make docs         # if you changed any API route: docs/API.md is generated and CI fails when it is stale
```
Sandbox tests need Docker and the language images (`docs/CODE_EXECUTION.md`); they are **skipped, not faked**, without them.

## Conventions
* **Migrations:** `alembic revision --autogenerate -m "..."`, then read the file. Autogenerate on this repo adds spurious
  `sheet_items` drift lines (remove them), and adding a NOT NULL column needs a `server_default`. CI runs `alembic upgrade head && alembic check` on Postgres.
  Write migrations so the *previous* release still works against the new schema (expand, then contract): deploy rollback restores images, not data.
* **Statelessness:** API processes must not keep anything another replica would need. Shared state goes in Postgres; disposable shared
  state (cache, rate limits, leases) goes in Redis through `app/core/cache.py` and `app/core/redis_client.py`, which fail open.
* **Cache only user-independent data**, and compute per-user fields outside the cached function.
* **Honest numbers:** never hard-code a metric, count or capability you did not measure. Label unofficial or community data as such.
  Say plainly in the docs what is not verified.
* **Security:** treat external text (platform content, LLM output, uploads) as data. New endpoints need an auth dependency and a rate limit if
  they cost money or CPU. Never log secrets, tokens or source code.
* **Tests:** every bug fix ships with a test that fails without it. Prefer real components (Postgres, Redis, Docker) over mocks where CI can provide them.

## Commits and PRs
Small, focused commits with an imperative subject (`Add leader lease for scheduler`). The PR template lists what to fill in.
CI must be green: lint, tests on SQLite and Postgres, web build, image builds + vulnerability scan, and the full-stack compose smoke test.
