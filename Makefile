.DEFAULT_GOAL := help
SHELL := /bin/bash

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## backend venv + web deps
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt "psycopg[binary]"
	cd web && npm ci

dev-api:  ## API on :18080 with a local SQLite db (migrated)
	cd backend && CODEMIND_DATABASE_URL=sqlite:///./dev.db .venv/bin/alembic upgrade head && CODEMIND_DATABASE_URL=sqlite:///./dev.db .venv/bin/uvicorn app.main:app --port 18080 --reload

dev-web:  ## web on :3000 (expects the API on :18080)
	cd web && NEXT_PUBLIC_API_URL=http://localhost:18080 npm run dev

lint:  ## ruff + tsc
	cd backend && .venv/bin/ruff check .
	cd web && npx tsc --noEmit

test:  ## backend (SQLite) + web + extension tests
	cd backend && .venv/bin/python -m pytest -q
	cd web && npm test
	node --test extension/test/*.test.mjs

test-pg:  ## backend tests on Postgres + Redis (throwaway containers that vanish on stop)
	-docker stop nx-test-pg nx-test-redis >/dev/null 2>&1
	docker run -d --rm --name nx-test-pg -e POSTGRES_USER=nexora -e POSTGRES_PASSWORD=nexora -e POSTGRES_DB=nexora_test -p 55432:5432 pgvector/pgvector:pg16 >/dev/null
	docker run -d --rm --name nx-test-redis -p 56379:6379 redis:7-alpine >/dev/null
	sleep 6; cd backend && NEXORA_TEST_DB=postgresql+psycopg://nexora:nexora@localhost:55432/nexora_test NEXORA_TEST_REDIS=redis://localhost:56379 .venv/bin/python -m pytest -q; status=$$?; docker stop nx-test-pg nx-test-redis >/dev/null 2>&1; exit $$status

docs:  ## regenerate docs/API.md from the code
	cd backend && PYTHONPATH=. .venv/bin/python scripts/gen_docs.py

up:  ## whole distributed stack (3 api, 2 web, worker, executor, db, redis, nginx) on :8080
	docker compose up -d --build --wait

down:  ## stop the stack (keeps volumes)
	docker compose down

smoke:  ## end-to-end checks against the running stack
	EXPECT_REPLICAS=$${API_REPLICAS:-3} WITH_SANDBOX=1 scripts/smoke.sh

chaos:  ## kill a replica / Redis / Postgres under load and report what users would see
	scripts/chaos.sh

observe:  ## add Prometheus + Grafana (:3001)
	docker compose --profile observability up -d prometheus grafana

.PHONY: help install dev-api dev-web lint test test-pg docs up down smoke chaos observe
