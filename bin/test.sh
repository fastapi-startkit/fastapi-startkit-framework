#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Lint ──────────────────────────────────────────────────────────────────────
echo "============================================================"
echo " Running: ruff lint checks"
echo "============================================================"
(cd "$ROOT/fastapi_startkit" && uv run ruff format --check src/ tests/)
(cd "$ROOT/fastapi_startkit" && uv run ruff check src/ tests/)

# ── Start MySQL via Docker Compose ────────────────────────────────────────────
echo "Starting test services..."
docker compose -f "$ROOT/docker-compose.yml" down --remove-orphans
docker compose -f "$ROOT/docker-compose.yml" up -d --wait

# Ensure MySQL is torn down on exit (even if tests fail)
trap 'echo "Stopping test services..."; docker compose -f "$ROOT/docker-compose.yml" down' EXIT

# ── Common DB env vars (match docker-compose.test.yml) ───────────────────────
export DB_HOST=127.0.0.1
export DB_PORT=3306
export POSTGRES_PORT=15432
export DB_DATABASE=database_app_test
export DB_USERNAME=app
export DB_PASSWORD=secret

echo ""
echo "============================================================"
echo " Running: fastapi_startkit package tests"
echo "============================================================"
(cd "$ROOT/fastapi_startkit" && uv run pytest tests)

echo ""
echo "============================================================"
echo " Running: example/config-app tests"
echo "============================================================"
(cd "$ROOT/example/config-app" && uv run pytest)

echo ""
echo "============================================================"
echo " Running: example/database-app tests"
echo "============================================================"
(cd "$ROOT/example/database-app" && uv run pytest)

echo ""
echo "============================================================"
echo " Running: example/agents tests"
echo "============================================================"
(cd "$ROOT/example/agents" && uv run pytest)
