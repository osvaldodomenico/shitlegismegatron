#!/usr/bin/env bash
# MEGATRON healthcheck — verifica API, Redis e TimescaleDB.
# Exit 0 = saudável, exit 1 = problema detectado.
# Loga em /var/log/megatron/healthcheck.log se diretório existir.

set -euo pipefail

LOG_DIR="/var/log/megatron"
LOG_FILE="$LOG_DIR/healthcheck.log"
COMPOSE_DIR="/opt/megatron"

mkdir -p "$LOG_DIR"

log() {
    local ts
    ts="$(date -Iseconds)"
    echo "[$ts] $*" | tee -a "$LOG_FILE"
}

FAILED=0

# 1. API health
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    log "API health: OK"
else
    log "API health: FAIL (curl /health retornou != 200)"
    FAILED=1
fi

# 2. Redis ping
if docker exec megatron-redis-1 redis-cli ping 2>/dev/null | grep -q PONG; then
    log "Redis ping: OK"
else
    log "Redis ping: FAIL"
    FAILED=1
fi

# 3. TimescaleDB
if docker exec megatron-timescaledb-1 pg_isready -U megatron 2>/dev/null; then
    log "TimescaleDB: OK"
else
    log "TimescaleDB: FAIL"
    FAILED=1
fi

# 4. Containers rodando
for svc in megatron-redis-1 megatron-timescaledb-1 megatron-api-1 megatron-collector-1 megatron-frontend-1 megatron-simulator-1; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${svc}$"; then
        log "Container $svc: AUSENTE"
        FAILED=1
    fi
done
[ "$FAILED" -eq 0 ] && log "Todos os containers: OK"

# 5. Disco
DISK_PCT=$(df / --output=pcent 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "$DISK_PCT" ] && [ "$DISK_PCT" -ge 90 ]; then
    log "DISCO: ALERTA — ${DISK_PCT}% usado (>= 90%)"
    FAILED=1
else
    log "Disco: ${DISK_PCT:-?}% usado"
fi

if [ "$FAILED" -eq 0 ]; then
    log "HEALTHCHECK: OK"
    exit 0
else
    log "HEALTHCHECK: DEGRADADO"
    exit 1
fi
