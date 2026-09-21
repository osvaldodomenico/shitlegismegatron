#!/usr/bin/env bash
# MEGATRON — vigia de producao (VPS do BI).
#
# Responde a UMA pergunta: o painel esta entregando dado agora?
# Checa collector vivo, as corridas configuradas respondendo e o frescor do
# dado. Manda e-mail quando algo cai e quando volta.
#
# Cron sugerido (a cada 5 min; na noite da apuracao, a cada 1 min):
#   */5 * * * * /opt/megatron/scripts/vigia_producao.sh >> /var/log/megatron-vigia-producao.log 2>&1
#
# Read-only. Estado em /var/tmp. NAO confundir com /root/vigia-producao.sh,
# que e do ShiftBI e nao tem relacao com este projeto.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ESTADO="${MEGATRON_VIGIA_PROD_ESTADO:-/var/tmp/megatron-vigia-producao.state}"
ENVFILE="${MEGATRON_RESEND_ENV:-/root/.disk_guard.env}"
MAILTO="${MEGATRON_MAILTO:-osvaldodomenico.apple@gmail.com}"
MAILFROM="MEGATRON <alertas@certificacao.shiftlegis.com.br>"
COMPOSE="${MEGATRON_COMPOSE:-$RAIZ/docker-compose.bi.yml}"
DOMINIO="${MEGATRON_DOMAIN:-megatron.shiftlegis.com.br}"

[ -f "$ENVFILE" ] && . "$ENVFILE"

PROBLEMAS=""
anotar() { PROBLEMAS="${PROBLEMAS}  - $1"$'\n'; }

enviar() {
    [ -z "${RESEND_KEY:-}" ] && { echo "$(date +%FT%T%z) SEM RESEND_KEY: $1"; return 1; }
    local corpo
    corpo=$(printf '%s' "$2" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    curl -sS -X POST https://api.resend.com/emails \
        -H "Authorization: Bearer $RESEND_KEY" -H "Content-Type: application/json" \
        -d "{\"from\":\"$MAILFROM\",\"to\":[\"$MAILTO\"],\"subject\":\"$1\",\"text\":\"$corpo\"}" \
        >/dev/null && echo "$(date +%FT%T%z) e-mail enviado: $1"
}

# ---------------------------------------------------------- 1) containers
for svc in collector api frontend redis timescaledb; do
    st="$(docker compose -f "$COMPOSE" ps --format '{{.Service}}|{{.Status}}' 2>/dev/null \
          | grep "^${svc}|" | cut -d'|' -f2)"
    case "$st" in
        "")        anotar "servico '$svc' NAO esta rodando" ;;
        Up*unhealthy*) anotar "servico '$svc' marcado unhealthy: $st" ;;
        Up*)       : ;;
        *)         anotar "servico '$svc' em estado inesperado: $st" ;;
    esac
done

# ------------------------------------------------- 2) heartbeat do collector
HB="$(docker exec megatron-collector-1 python /app/healthcheck.py 2>&1 </dev/null)"
if [ $? -ne 0 ]; then
    anotar "collector sem batimento: $HB"
fi

# --------------------------------------------- 3) as corridas configuradas
CORRIDAS="$(python3 - "$RAIZ/.env" <<'PY'
import sys
env = {}
for linha in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    if "=" in linha and not linha.strip().startswith("#"):
        k, _, v = linha.partition("=")
        env[k.strip()] = v.strip()
ufs = [u.strip() for u in env.get("UFS", "").split(",") if u.strip()]
cargos = [c.strip() for c in env.get("CARGOS", "").split(",") if c.strip()]
# presidente so existe em "br"; os demais so por UF — mesma regra do collector
for uf in ufs:
    for cargo in cargos:
        if (cargo == "presidente") == (uf == "br"):
            print(f"{uf}/{cargo}")
PY
)"
[ -z "$CORRIDAS" ] && anotar "nao consegui ler UFS/CARGOS do .env"

for c in $CORRIDAS; do
    code="$(curl -s -o /tmp/mvp.json -w '%{http_code}' --max-time 30 "https://$DOMINIO/resultados/$c")"
    if [ "$code" != "200" ]; then
        anotar "corrida $c respondeu HTTP $code"
        continue
    fi
    # Dado envelhecido so e problema enquanto a apuracao nao fechou: com
    # pst=100 a fonte legitimamente para de mudar.
    aviso="$(python3 - <<PY
import json
from datetime import datetime
d = json.load(open("/tmp/mvp.json"))
if "detail" in d:
    print("sem dado: " + str(d["detail"])); raise SystemExit
pst = float(str(d.get("pst", "0")).replace(".", "").replace(",", "."))
if pst >= 100:
    raise SystemExit
try:
    ger = datetime.strptime(f"{d['dg']} {d['hg']}", "%d/%m/%Y %H:%M:%S")
    minutos = (datetime.now() - ger).total_seconds() / 60
    if minutos > 15:
        print(f"boletim parado ha {minutos:.0f} min (pst={pst:.2f}%)")
except Exception:
    pass
PY
)"
    [ -n "$aviso" ] && anotar "corrida $c: $aviso"
done

# ------------------------------------------------------------- 4) resultado
ANTERIOR="ok"; [ -f "$ESTADO" ] && ANTERIOR="$(cat "$ESTADO")"

if [ -n "$PROBLEMAS" ]; then
    echo "$(date +%FT%T%z) PROBLEMA:"; printf '%s' "$PROBLEMAS"
    if [ "$ANTERIOR" != "falha" ]; then
        enviar "MEGATRON: producao com problema" \
"Detectado em $(date +%FT%T%z) na VPS do BI:

$PROBLEMAS
Conferir:
  docker compose -f $COMPOSE ps
  docker logs --tail 50 megatron-collector-1
  $RAIZ/.claude/checkup.sh"
    fi
    echo "falha" > "$ESTADO"
else
    echo "$(date +%FT%T%z) ok — $(echo "$CORRIDAS" | wc -w | tr -d ' ') corrida(s) respondendo"
    if [ "$ANTERIOR" = "falha" ]; then
        enviar "MEGATRON: producao normalizada" \
"Tudo respondendo de novo em $(date +%FT%T%z)."
    fi
    echo "ok" > "$ESTADO"
fi
