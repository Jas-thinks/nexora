# Testing

Backend: `cd backend && .venv/bin/python -m pytest` · Web: `cd web && npm test`.
Counts and what they prove are in docs/product/COMPLETE_FEATURE_INVENTORY.md. Strategy: real recorded response fixtures through `httpx.MockTransport` for adapters; behaviour tests with explicit failure paths (retries, 429, unknown handle, still-judging submission, oversize upload, authz 404/403, replay attack); cross-checks against independent references (Bellman-Ford, brute-force knapsack/window); property-style repeats for random inputs; leakage test for evaluation; cache-invalidation tests. Bugs found by tests/measurements during development are listed in docs/ROADMAP.md.
Not covered: browser E2E in CI (screenshots were taken manually with Playwright), contract tests against live platforms in CI, load tests in CI, security scanning.
