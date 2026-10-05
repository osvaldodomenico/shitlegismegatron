#!/usr/bin/env bash
# Dump completo do banco do MEGATRON na propria VPS (sem depender do HD externo).
#   /opt/megatron/backups/db/megatron-<timestamp>.dump   (pg_dump -Fc, comprimido)
#   /opt/megatron/backups/db/megatron-latest.dump         (copia do mais recente)
# Retencao: os 12 mais recentes (6 h a cada 30 min) + 1 por dia em diario/.
# Valida: pg_restore -l precisa listar o conteudo; dump < 50 MB e suspeito.
set -uo pipefail
DIR=/opt/megatron/backups/db
mkdir -p "$DIR/diario"
carimbo=$(date +%Y%m%d-%H%M%S)
alvo="$DIR/megatron-$carimbo.dump"
if ! docker exec megatron-timescaledb-1 pg_dump -U megatron -d megatron -Fc > "$alvo.part" 2>/tmp/dump_db.err; then
    echo "$(date +%FT%T) FALHA pg_dump: $(tail -1 /tmp/dump_db.err)"; rm -f "$alvo.part"; exit 1
fi
mv "$alvo.part" "$alvo"
tam=$(stat -c %s "$alvo")
if [ "$tam" -lt 50000000 ] || ! docker exec -i megatron-timescaledb-1 pg_restore -l < "$alvo" >/dev/null 2>&1; then
    echo "$(date +%FT%T) DUMP SUSPEITO ($tam bytes ou ilegivel): $alvo"; exit 1
fi
cp "$alvo" "$DIR/megatron-latest.dump"
cp -n "$alvo" "$DIR/diario/megatron-$(date +%Y%m%d).dump" 2>/dev/null || true
ls -t "$DIR"/megatron-2*.dump | tail -n +13 | xargs -r rm -f
echo "$(date +%FT%T) ok $(du -h "$alvo" | cut -f1) | tabelas: $(docker exec -i megatron-timescaledb-1 pg_restore -l < "$alvo" | grep -c 'TABLE DATA') | livre: $(df -h /opt | tail -1 | awk '{print $4}')"

# Base do 2o turno (megatron_t2, 25/10), quando existir. Comeca pequena (so locais_votacao),
# entao vale so a leitura pelo pg_restore -l; mesma retencao de 12.
if docker exec megatron-timescaledb-1 psql -U megatron -d megatron -Atc "SELECT 1 FROM pg_database WHERE datname='megatron_t2'" | grep -q 1; then
    alvo2="$DIR/megatron_t2-$carimbo.dump"
    if docker exec megatron-timescaledb-1 pg_dump -U megatron -d megatron_t2 -Fc > "$alvo2.part" 2>/tmp/dump_db_t2.err \
       && mv "$alvo2.part" "$alvo2" && docker exec -i megatron-timescaledb-1 pg_restore -l < "$alvo2" >/dev/null 2>&1; then
        ls -t "$DIR"/megatron_t2-2*.dump | tail -n +13 | xargs -r rm -f
        echo "$(date +%FT%T) ok t2 $(du -h "$alvo2" | cut -f1)"
    else
        echo "$(date +%FT%T) FALHA dump t2: $(tail -1 /tmp/dump_db_t2.err)"; rm -f "$alvo2.part"; exit 1
    fi
fi
