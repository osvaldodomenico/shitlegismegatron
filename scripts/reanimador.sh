#!/usr/bin/env bash
# REANIMADOR — reinicia sozinho o que parar, travar ou adoecer (cron a cada 5 min).
#
# Para cada servico: container tem que estar "Up" (nem Exited, nem Restarting,
# nem unhealthy) e, nos coletores, o batimento no Redis tem que existir (cada
# coletor grava a chave com TTL = 3 ciclos; chave ausente = travou).
# Acao: `docker compose restart <svc>` (ou `up -d` se o container sumiu), no
# maximo UMA vez a cada COOLDOWN segundos por servico — reiniciar em loop
# esconderia um problema de verdade. Toda acao vai para o log e por e-mail.
# Tambem avisa (sem agir) se o disco baixar de 20 GB livres.
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="${MEGATRON_COMPOSE:-$RAIZ/docker-compose.bi.yml}"
ENVFILE="${MEGATRON_RESEND_ENV:-/root/.disk_guard.env}"
MAILTO="${MEGATRON_MAILTO:-osvaldodomenico.apple@gmail.com}"
MAILFROM="MEGATRON <alertas@certificacao.shiftlegis.com.br>"
ESTADO_DIR=/var/tmp/megatron-reanimador
COOLDOWN="${MEGATRON_REANIMADOR_COOLDOWN:-900}"
mkdir -p "$ESTADO_DIR"
[ -f "$ENVFILE" ] && . "$ENVFILE"

log() { echo "$(date +%FT%T%z) $*"; }
enviar() {
    [ -z "${RESEND_KEY:-}" ] && return 0
    local corpo; corpo=$(printf '%s' "$2" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    curl -sS -m 20 -X POST https://api.resend.com/emails \
        -H "Authorization: Bearer $RESEND_KEY" -H "Content-Type: application/json" \
        -d "{\"from\":\"$MAILFROM\",\"to\":[\"$MAILTO\"],\"subject\":\"$1\",\"text\":\"$corpo\"}" >/dev/null
}

# servico|chave do heartbeat no Redis (vazio = so o container)
SERVICOS="redis|
timescaledb|
api|
frontend|
collector|megatron:heartbeat:collector
collector_municipios|megatron:heartbeat:municipios
collector_urnas|megatron:heartbeat:urnas
collector_bu|megatron:heartbeat:bu
bi_sync|megatron:heartbeat:bi_sync"

status_de() { docker compose -f "$COMPOSE" ps --format '{{.Service}}|{{.Status}}' 2>/dev/null | grep "^$1|" | cut -d'|' -f2; }
batimento() { [ -z "$1" ] && return 0; [ -n "$(docker exec megatron-redis-1 redis-cli get "$1" 2>/dev/null)" ]; }

reanimar() {   # $1 servico, $2 motivo
    local marca="$ESTADO_DIR/$1.ultimo" agora; agora=$(date +%s)
    if [ -f "$marca" ] && [ $(( agora - $(cat "$marca") )) -lt "$COOLDOWN" ]; then
        log "$1: $2 — ja reiniciado ha menos de ${COOLDOWN}s, aguardando"; return
    fi
    echo "$agora" > "$marca"
    log "$1: $2 — REINICIANDO"
    if [ -z "$(status_de "$1")" ]; then
        docker compose -f "$COMPOSE" up -d "$1" >/dev/null 2>&1
    else
        docker compose -f "$COMPOSE" restart "$1" >/dev/null 2>&1
    fi
    sleep 20
    log "$1: depois do reinicio -> $(status_de "$1")"
    enviar "MEGATRON: $1 reiniciado pelo reanimador" "Servico: $1
Motivo: $2
Quando: $(date +%FT%T%z)
Estado depois: $(status_de "$1")
Ultimas linhas do log:
$(docker compose -f "$COMPOSE" logs --tail 8 "$1" 2>/dev/null | tail -8)"
}

for linha in $SERVICOS; do
    svc="${linha%%|*}"; chave="${linha#*|}"
    st="$(status_de "$svc")"
    case "$st" in
        "")                reanimar "$svc" "container ausente" ; continue ;;
        Up*unhealthy*)     reanimar "$svc" "unhealthy: $st" ; continue ;;
        Up*)               ;;
        *)                 reanimar "$svc" "estado '$st'" ; continue ;;
    esac
    # Container de pe ha pouco (acabou de subir): da tempo de gravar o 1o batimento.
    case "$st" in *"second"*|*"Less than a minute"*|*"About a minute"*|*" 2 minutes"*|*" 3 minutes"*|*" 4 minutes"*) continue ;; esac
    if ! batimento "$chave"; then
        reanimar "$svc" "sem batimento no Redis ($chave)"
    fi
done

# Disco
livre_gb=$(df -BG /opt | tail -1 | awk '{print $4}' | tr -d 'G')
if [ "${livre_gb:-999}" -lt 20 ]; then
    marca="$ESTADO_DIR/disco.ultimo"; agora=$(date +%s)
    if [ ! -f "$marca" ] || [ $(( agora - $(cat "$marca") )) -ge 3600 ]; then
        echo "$agora" > "$marca"; log "DISCO: ${livre_gb} GB livres"
        enviar "MEGATRON: disco com ${livre_gb} GB livres" "Coleta de urnas pode parar. Ver /opt/megatron/dados e /opt/megatron/backups."
    fi
fi
