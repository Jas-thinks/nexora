#!/usr/bin/env bash
# Deploy a specific image tag on the VM, verify it, and roll back automatically if verification fails.
#   deploy.sh <image-tag>          run from /opt/nexora (the CD workflow copies compose files + scripts here first)
set -euo pipefail
TAG="${1:?usage: deploy.sh <image-tag>}"
cd "$(dirname "$0")/../.."
[ -f .env ] || { echo ".env missing: create it from .env.example"; exit 1; }
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
PREV="$(grep -E '^IMAGE_TAG=' .env | cut -d= -f2- || true)"
setenv() { if grep -q '^IMAGE_TAG=' .env; then sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=$1|" .env; else echo "IMAGE_TAG=$1" >> .env; fi; }

echo "== deploying $TAG (previous: ${PREV:-none})"
setenv "$TAG"
$COMPOSE pull --quiet
$COMPOSE up -d --no-build --remove-orphans --wait --wait-timeout 240 || true     # `migrate` runs once before api/worker; api replicas are then replaced one container at a time by compose

if EXPECT_REPLICAS="$(grep -E '^API_REPLICAS=' .env | cut -d= -f2- || echo 3)" scripts/smoke.sh "http://localhost:${LB_PORT:-8080}" 2>&1; then
  echo "$TAG" > .last_good_tag; docker image prune -f >/dev/null; echo "== deployed $TAG"
else
  echo "== smoke test FAILED for $TAG"
  if [ -n "${PREV:-}" ] && [ "$PREV" != "$TAG" ]; then
    echo "== rolling back to $PREV (database migrations are forward-only: see docs/DEPLOYMENT.md)"
    setenv "$PREV"; $COMPOSE pull --quiet; $COMPOSE up -d --no-build --remove-orphans --wait --wait-timeout 240 || true
  fi
  exit 1
fi
