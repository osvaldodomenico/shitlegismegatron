#!/usr/bin/env bash
# MEGATRON — vigia do codigo da eleicao de 2026.
#
# O TSE ainda nao publicou o codigo da geral de 04/10/2026. Sem ele o
# collector da 404 em tudo. Este vigia le o indice oficial de hora em hora e
# manda e-mail assim que aparecer um pleito NAO SUPLEMENTAR em 2026 — ou
# quando o conjunto de pleitos de 2026 mudar.
#
# Cron sugerido:  17 * * * * /opt/megatron/scripts/vigia_ele.sh >> /var/log/megatron-vigia-ele.log 2>&1
#
# Nao escreve nada em producao. Estado em /var/tmp.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ESTADO="${MEGATRON_VIGIA_ESTADO:-/var/tmp/megatron-vigia-ele.json}"
ENVFILE="${MEGATRON_RESEND_ENV:-/root/.disk_guard.env}"
MAILTO="${MEGATRON_MAILTO:-osvaldodomenico.apple@gmail.com}"
MAILFROM="MEGATRON <alertas@certificacao.shiftlegis.com.br>"
ANO="${MEGATRON_ANO_ELEICAO:-2026}"

[ -f "$ENVFILE" ] && . "$ENVFILE"

enviar() {  # $1=assunto  $2=corpo
    if [ -z "${RESEND_KEY:-}" ]; then
        echo "$(date +%FT%T%z) SEM RESEND_KEY — nao enviei: $1"
        return 1
    fi
    local corpo
    corpo=$(printf '%s' "$2" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    curl -sS -X POST https://api.resend.com/emails \
        -H "Authorization: Bearer $RESEND_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"from\":\"$MAILFROM\",\"to\":[\"$MAILTO\"],\"subject\":\"$1\",\"text\":\"$corpo\"}" \
        >/dev/null && echo "$(date +%FT%T%z) e-mail enviado: $1"
}

DESCOBRIR="python3 $RAIZ/scripts/descobrir_ele.py --ano $ANO"

ASSINATURA="$($DESCOBRIR --assinatura 2>/dev/null)"
if [ -z "$ASSINATURA" ]; then
    echo "$(date +%FT%T%z) indice do TSE indisponivel — tento de novo no proximo ciclo"
    exit 0   # indisponibilidade passageira nao e alarme
fi

# exit 0 = existe pleito NAO suplementar em $ANO, ou seja, a geral apareceu.
GERAL="$($DESCOBRIR --resumo-geral 2>/dev/null)"

ANTERIOR=""
[ -f "$ESTADO" ] && ANTERIOR="$(cat "$ESTADO" 2>/dev/null)"

if [ -n "$GERAL" ]; then
    if [ "$ANTERIOR" != "$ASSINATURA" ]; then
        enviar "MEGATRON: eleicao geral de $ANO PUBLICADA no TSE" \
"O TSE publicou pleito nao suplementar em $ANO.

$GERAL

Proximo passo — no .env da VPS BI (/opt/megatron/.env):
  ELE_1T_BR=<codigo do pleito com Presidente>
  ELE_1T=<codigo do pleito com Governador>
  ELE_2T=<codigo do 2o turno>
  TSE_BASE_URL=https://resultados.tse.jus.br/oficial/<ciclo>

Depois: docker compose -f docker-compose.bi.yml up -d collector api
E rodar: .claude/checkup.sh"
    else
        echo "$(date +%FT%T%z) geral de $ANO ja conhecida, sem mudanca"
    fi
elif [ -n "$ANTERIOR" ] && [ "$ANTERIOR" != "$ASSINATURA" ]; then
    enviar "MEGATRON: indice de eleicoes do TSE mudou ($ANO)" \
"Os pleitos de $ANO mudaram, mas ainda sao todos suplementares.
Vale conferir: scripts/descobrir_ele.py --ano $ANO"
else
    echo "$(date +%FT%T%z) sem geral de $ANO ainda (so suplementares)"
fi

printf '%s' "$ASSINATURA" > "$ESTADO"
