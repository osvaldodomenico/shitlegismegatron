#!/usr/bin/env bash
# Espelha a coleta da noite da VPS para o HD externo do Domenico (04/10/2026):
#   urnas/  -> dados/urnas da VPS (boletins por secao, incremental via rsync)
#   tse/    -> dados/tse (cadastro de locais de votacao, zip + CSVs)
#   banco/  -> pg_dump completo (formato custom, comprimido): <timestamp> + latest
# Roda em loop (ESPELHO_INTERVALO s, padrao 1800). Um ciclo so copia o que mudou.
set -uo pipefail
DESTINO="${ESPELHO_DESTINO:-/Volumes/BEE MAC/MEGATRON-2026}"
INTERVALO="${ESPELHO_INTERVALO:-1800}"
VPS="${ESPELHO_VPS:-vps2}"

ciclo() {
    local ini=$(date +%s) carimbo=$(date +%Y%m%d-%H%M%S)
    [ -d "$DESTINO" ] || { echo "$(date +%FT%T) destino ausente: $DESTINO (HD desmontado?)"; return 1; }
    rsync -az --partial --timeout=120 "$VPS:/opt/megatron/dados/urnas/" "$DESTINO/urnas/" 2>&1 | tail -2
    rsync -az --partial --timeout=120 "$VPS:/opt/megatron/dados/tse/"   "$DESTINO/tse/"   2>&1 | tail -2
    ssh -o ConnectTimeout=20 "$VPS" 'docker exec megatron-timescaledb-1 pg_dump -U megatron -d megatron -Fc' > "$DESTINO/banco/megatron-$carimbo.dump.part" \
        && mv "$DESTINO/banco/megatron-$carimbo.dump.part" "$DESTINO/banco/megatron-$carimbo.dump" \
        && cp "$DESTINO/banco/megatron-$carimbo.dump" "$DESTINO/banco/megatron-latest.dump"
    # Validacao: contagem de arquivos aqui x na VPS, e o dump precisa ser um
    # arquivo pg_dump legivel (pg_restore -l) quando houver pg_restore local.
    local aqui remoto estado="ok"
    aqui=$(find "$DESTINO/urnas" -type f | wc -l | tr -d ' ')
    remoto=$(ssh -o ConnectTimeout=20 "$VPS" 'find /opt/megatron/dados/urnas -type f | wc -l' 2>/dev/null | tr -d ' ')
    [ -n "$remoto" ] && [ "$aqui" -lt $(( remoto - 2000 )) ] && estado="ATRASADO (${aqui} aqui, ${remoto} na VPS)"
    if command -v pg_restore >/dev/null 2>&1; then
        pg_restore -l "$DESTINO/banco/megatron-latest.dump" >/dev/null 2>&1 || estado="DUMP ILEGIVEL"
    fi
    [ "$(stat -f %z "$DESTINO/banco/megatron-latest.dump" 2>/dev/null || echo 0)" -gt 50000000 ] || estado="DUMP PEQUENO DEMAIS"
    echo "$(date +%FT%T) ciclo $estado em $(( $(date +%s) - ini ))s | urnas: $aqui arquivos (VPS: ${remoto:-?}), $(du -sh "$DESTINO/urnas" | cut -f1) | banco: $(du -h "$DESTINO/banco/megatron-latest.dump" | cut -f1)"
    # Guarda so os 6 dumps mais recentes (cada um ~150 MB+).
    ls -t "$DESTINO"/banco/megatron-2*.dump 2>/dev/null | tail -n +7 | xargs -I{} rm -f {}
}

if [ "${1:-}" = "--uma-vez" ]; then ciclo; exit $?; fi
while true; do ciclo; sleep "$INTERVALO"; done
