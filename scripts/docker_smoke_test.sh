#!/usr/bin/env bash
# Milestone 24 scripted smoke test.
#
# Bash — needs WSL, Git Bash, or a Linux/macOS shell with Docker
# installed. If you're in plain PowerShell, use the equivalent step-by-
# step commands in docs/docker.md instead; this script and that doc
# section do exactly the same checks.
set -euo pipefail

echo "== Milestone 24 Docker smoke test =="

if [ -z "${SECRET_KEY:-}" ]; then
    export SECRET_KEY="docker-smoke-test-do-not-use-in-production-$(date +%s)"
    echo "SECRET_KEY not set in your environment — using a throwaway value for this smoke test only."
fi

PORT="${API_PORT:-8000}"

echo "-- Building image --"
docker compose build

echo "-- Starting container --"
docker compose up -d

cleanup() {
    echo "-- Tearing down --"
    docker compose down -v
}
trap cleanup EXIT

echo "-- Waiting for the healthcheck to pass --"
for i in $(seq 1 30); do
    container_id="$(docker compose ps -q api)"
    status="$(docker inspect --format='{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo starting)"
    if [ "$status" = "healthy" ]; then
        echo "Container is healthy."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "Container did not become healthy within 60s." >&2
        docker compose logs api
        exit 1
    fi
    sleep 2
done

echo "-- GET /health --"
curl -sf "http://localhost:${PORT}/health" | grep -q '"status":"ok"' && echo "OK"

echo "-- POST /assets (register a real asset) --"
response="$(curl -sf -X POST "http://localhost:${PORT}/assets" \
    -H "Content-Type: application/json" \
    -d '{"identifier": "docker-smoke-test-01"}')"
echo "$response" | grep -q '"identifier":"docker-smoke-test-01"' && echo "OK"

echo "-- GET /docs (Swagger UI) --"
curl -sf "http://localhost:${PORT}/docs" > /dev/null && echo "OK"

echo "== All smoke tests passed =="
