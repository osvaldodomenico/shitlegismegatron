#!/usr/bin/env bash
# MEGATRON backup — pg_dump do TimescaleDB → gzip em /var/backups/megatron/
# Mantém últimos 7. Loga em /var/log/megatron/backup.log.

set -euo pipefail

BACKUP_DIR="/var/backups/megatron"
LOG_FILE="/var/log/megatron/backup.log"
KEEP=7
TS=$(date -u +%Y%m%d-%H%M%S)
FILENAME="${BACKUP_DIR}/megatron-${TS}.sql.gz"

mkdir -p "$BACKUP_DIR"

log() {
    local msg
    msg="[$(date -Iseconds)] $*"
    if [ -w "$LOG_FILE" ] || mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null; then
        echo "$msg" | tee -a "$LOG_FILE"
    else
        echo "$msg"
    fi
}

log "Iniciando backup → $FILENAME"

# Dump direto do container timescaledb
docker exec megatron-timescaledb-1 \
    pg_dump -U megatron -d megatron --no-owner --clean --if-exists 2>/tmp/pg_dump_err \
    | gzip > "$FILENAME"

RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ]; then
    log "ERRO: pg_dump retornou $RC — $(cat /tmp/pg_dump_err)"
    rm -f "$FILENAME"
    exit 1
fi

SIZE=$(du -h "$FILENAME" | cut -f1)
log "Backup OK: $FILENAME ($SIZE)"

# Mantém últimos N
cd "$BACKUP_DIR"
ls -1t megatron-*.sql.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
REMAINING=$(ls -1 megatron-*.sql.gz 2>/dev/null | wc -l | tr -d ' ')
log "Backups retidos: $REMAINING (meta: $KEEP)"
