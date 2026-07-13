#!/usr/bin/env bash
# MEGATRON stack restart — reinicia em ordem segura (DB → cache → coletor → API → frontend)
# Espera healthcheck entre cada etapa.

set -euo pipefail

COMPOSE_DIR="/opt/megatron"

cd "$COMPOSE_DIR"

echo "=== Parando collector e API ==="
docker compose stop collector api frontend || true

echo "=== Reiniciando TimescaleDB e Redis ==="
docker compose restart timescaledb redis

echo "=== Aguardando TimescaleDB healthy (até 60s) ==="
for i in $(seq 1 60); do
    if docker exec megatron-timescaledb-1 pg_isready -U megatron >/dev/null 2>&1; then
        echo "TimescaleDB ready em ${i}s"
        break
    fi
    sleep 1
done

echo "=== Aguardando Redis ping ==="
for i in $(seq 1 30); do
    if docker exec megatron-redis-1 redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "Redis ready em ${i}s"
        break
    fi
    sleep 1
done

echo "=== Subindo collector, API e frontend ==="
docker compose up -d collector api frontend

echo "=== Aguardando API health ==="
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "API health OK em ${i}s"
        break
    fi
    sleep 1
done

echo "=== Status final ==="
docker compose ps

echo "=== Healthcheck ==="
bash "$COMPOSE_DIR/scripts/healthcheck.sh"
