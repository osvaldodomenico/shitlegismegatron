#!/usr/bin/env bash
# MEGATRON — descobre os codigos de eleicao (ELE) publicados pelo TSE.
#
# O TSE nao expoe um indice legivel dos codigos; a forma confiavel de
# descobri-los eh sondar a propria CDN. Este script varre uma faixa de
# codigos e imprime os que respondem 200 para presidente (abrangencia "br")
# e para governador (abrangencia de uma UF).
#
# Uso:
#   scripts/descobrir_ele.sh                 # ciclo ele2026, faixa 500-700
#   scripts/descobrir_ele.sh ele2022 540 550 # valida contra 2022 (sanity check)
#
# Saida esperada em 2022 (prova de que o script funciona):
#   544  br/presidente
#   546  sp/governador
#   547  sp/governador     <- 2o turno
#
# Preencher .env com o resultado:
#   ELE_1T_BR=<codigo que apareceu em br/presidente>
#   ELE_1T=<codigo que apareceu em sp/governador>

set -uo pipefail

CICLO="${1:-ele2026}"
INICIO="${2:-500}"
FIM="${3:-700}"
UF_TESTE="${UF_TESTE:-sp}"
BASE="https://resultados.tse.jus.br/oficial/${CICLO}"

probe() {  # $1=ele  $2=abr  $3=cargo
    local ele="$1" abr="$2" cargo="$3"
    local pad
    pad="$(printf '%06d' "$ele")"
    local url="${BASE}/${ele}/dados-simplificados/${abr}/${abr}-c${cargo}-e${pad}-r.json"
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' \
        -A 'Megatron/1.0 (Election Monitor)' \
        -e 'https://resultados.tse.jus.br/' \
        --max-time 10 "$url")"
    [ "$code" = "200" ] && echo "$url"
}

echo "Varrendo ${CICLO}, codigos ${INICIO}..${FIM} (UF de teste: ${UF_TESTE})"
echo

ACHOU=0
for ele in $(seq "$INICIO" "$FIM"); do
    if url="$(probe "$ele" "br" "0001")" && [ -n "$url" ]; then
        echo "  ELE_1T_BR=${ele}   (presidente, nacional)"
        echo "      $url"
        ACHOU=1
    fi
    if url="$(probe "$ele" "$UF_TESTE" "0003")" && [ -n "$url" ]; then
        echo "  ELE_1T=${ele}      (governador, por UF)"
        echo "      $url"
        ACHOU=1
    fi
done

echo
if [ "$ACHOU" -eq 0 ]; then
    echo "Nenhum codigo respondeu 200. O TSE ainda nao abriu a divulgacao"
    echo "deste ciclo, ou a faixa varrida esta errada."
    exit 1
fi
echo "Havendo mais de um codigo por abrangencia, o MAIOR costuma ser o 2o turno."
