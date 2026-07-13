#!/usr/bin/env bash
# Instala crontab de manutenção do MEGATRON:
# - healthcheck a cada 15 minutos
# - backup diário às 03:00
# Logs em /var/log/megatron/

set -euo pipefail

CRON_FILE="/etc/cron.d/megatron"
SCRIPTS_DIR="/opt/megatron/scripts"
LOG_DIR="/var/log/megatron"

# Garante diretório de logs existe
mkdir -p "$LOG_DIR"

cat > "$CRON_FILE" <<EOF
# MEGATRON — manutenção automatica
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Healthcheck a cada 15 minutos
*/15 * * * * root bash ${SCRIPTS_DIR}/healthcheck.sh >> ${LOG_DIR}/healthcheck.log 2>&1

# Backup diario do TimescaleDB as 03:00
0 3 * * * root bash ${SCRIPTS_DIR}/backup_db.sh >> ${LOG_DIR}/backup.log 2>&1
EOF

chmod 0644 "$CRON_FILE"

# Recarrega cron (debian/ubuntu)
if command -v systemctl >/dev/null 2>&1; then
    systemctl reload cron 2>/dev/null || systemctl reload crond 2>/dev/null || true
fi

echo "Crontab instalado em $CRON_FILE"
echo
echo "Entradas ativas:"
crontab -l 2>/dev/null || true
cat "$CRON_FILE"
