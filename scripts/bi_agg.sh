#!/usr/bin/env bash
# Agregacao do Legis Inteligencia (BI) para 2026 — cron do host a cada 20 min.
#
# Roda so quando o bi_sync marcou megatron:bi:agg_pendente E esta ocioso (fim
# de rodada). Executa o pipeline do PROPRIO BI (scripts/populate_agg_tables.php:
# map, escola, municipio, top) num container TEMPORARIO com a imagem do BI e o
# codigo montado so-leitura — o container em producao do BI nao e alterado.
# Depois limpa do cache do BI somente as chaves que mencionam 2026.
set -uo pipefail
ANO="${BI_AGG_ANO:-2026}"; UF="${BI_AGG_UF:-SP}"
CODE=/etc/easypanel/projects/shiftworks/shiftlegisbi/code
LOCK=/var/tmp/megatron-bi-agg.lock
log() { echo "$(date +%FT%T%z) $*"; }

exec 9>"$LOCK"; flock -n 9 || { log "ja rodando"; exit 0; }
pend="$(docker exec megatron-redis-1 redis-cli get megatron:bi:agg_pendente 2>/dev/null)"
[ -z "$pend" ] && exit 0
docker exec megatron-redis-1 redis-cli get megatron:heartbeat:bi_sync | grep -q '"ocioso": true' || { log "bi_sync ainda carregando; agrega na proxima"; exit 0; }

APP=$(docker ps --format '{{.Names}}' | grep '^shiftworks_shiftlegisbi\.')
IMG=$(docker inspect "$APP" --format '{{.Config.Image}}')
NET=$(docker inspect "$APP" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')
ENVS=$(docker exec "$APP" printenv | grep -E '^(DB_|REDIS_)' | sed 's/^/-e /' | tr '\n' ' ')

log "agregando ano=$ANO uf=$UF (pendente desde $pend)"
ini=$(date +%s); ok=1
for step in map escola municipio top; do
    # shellcheck disable=SC2086
    if ! docker run --rm --network "$NET" $ENVS -v "$CODE:/var/www/html:ro" -w /var/www/html "$IMG" \
         php scripts/populate_agg_tables.php --step="$step" --ano="$ANO" --uf="$UF" --force > "/var/tmp/bi_agg_$step.log" 2>&1; then
        ok=0; log "FALHA no passo $step: $(tail -3 /var/tmp/bi_agg_$step.log | tr '\n' ' ')"; break
    fi
    log "passo $step ok: $(grep -E 'CONCLU|OK' /var/tmp/bi_agg_$step.log | tail -1)"
done
[ "$ok" = 1 ] || exit 1

# Cache do BI: so o que menciona 2026.
RP=$(docker exec "$APP" printenv REDIS_PASSWORD); RH=$(docker exec "$APP" printenv REDIS_HOST)
RC=$(docker ps --format '{{.Names}}' | grep -i "$(echo "$RH" | sed 's/shiftworks_//')" | head -1)
if [ -n "$RC" ]; then
    n=$(docker exec -e REDISCLI_AUTH="$RP" "$RC" redis-cli --scan --pattern '*2026*' | wc -l)
    docker exec -e REDISCLI_AUTH="$RP" "$RC" sh -c "redis-cli --scan --pattern '*2026*' | xargs -r redis-cli del" >/dev/null
    log "cache redis do BI: $n chave(s) de 2026 removidas"
fi
docker exec "$APP" sh -c "grep -l 2026 /var/www/html/cache_store/* /var/www/html/public/cache/*.json 2>/dev/null | xargs -r rm -f"

# So limpa a pendencia se o bi_sync nao marcou de novo durante a agregacao.
[ "$(docker exec megatron-redis-1 redis-cli get megatron:bi:agg_pendente)" = "$pend" ] && docker exec megatron-redis-1 redis-cli del megatron:bi:agg_pendente >/dev/null
log "agregacao concluida em $(( $(date +%s) - ini ))s"
