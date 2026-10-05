#!/usr/bin/env bash
# LIGA a coleta do 2o turno (MEGATRON -> Legis Inteligencia). Rodar na VPS BI.
#
#   scripts/ligar_turno2.sh               liga (pede confirmacao)
#   scripts/ligar_turno2.sh --verificar   confere se o 1o turno no BI segue intacto
#   scripts/ligar_turno2.sh --ensaio      so os passos de seguranca (1-3), sem trocar nada
#
# Antes de trocar: (1) dump do MEGATRON (fonte do 1o turno) recente e legivel;
# (2) backup das linhas de presidente 2026 no BI com restauracao testada;
# (3) totais de referencia do 1o turno gravados. Depois anexa o .env.turno2
# (gerado pelo vigia_turno2) ao .env e sobe os 4 servicos da coleta.
# Desfazer: scripts/desligar_turno2.sh
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
COMPOSE="docker-compose.bi.yml"
SERVICOS="collector_municipios collector_urnas collector_bu bi_sync"
BK="$RAIZ/backups"
MYSQLC=$(docker ps --format '{{.Names}}' | grep 'mysql_shiftbi\.1')
my() { docker exec -i "$MYSQLC" sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' 2>/dev/null; }
log() { echo "$(date +%T) $*"; }

referencia() {   # totais do 1o turno de 2026 no BI (presidente e o unico cargo de SP no 2o turno)
    my <<'SQL'
SELECT 'estadual', cargo, COUNT(*), SUM(votos) FROM shiftBI.resultados_candidato WHERE ano=2026 AND turno=1 GROUP BY cargo ORDER BY cargo;
SELECT 'municipio_pres', COUNT(*), SUM(votos) FROM shiftBI.resultados_candidato_municipio WHERE ano=2026 AND turno=1 AND cargo='presidente';
SELECT 'zona_pres', COUNT(*), SUM(votos) FROM shiftBI.resultados_candidato_municipio_zona WHERE ano=2026 AND turno=1 AND cargo='presidente';
SELECT 'detalhes_pres', COUNT(*), SUM(comparecimento) FROM shiftBI.detalhes_votacao_municipio WHERE ano=2026 AND turno=1 AND cargo='presidente';
SELECT 'secao_pres_jundiai', COUNT(*), SUM(votos) FROM shiftBI.resultados_candidato_secao WHERE ano=2026 AND turno=1 AND id_municipio_tse=66192 AND cargo='presidente';
SQL
}

if [ "${1:-}" = "--verificar" ]; then
    base=$(ls -t "$BK"/bi_turno1_referencia-*.txt 2>/dev/null | head -1)
    [ -n "$base" ] || { echo "sem referencia gravada (o 2o turno foi ligado por este script?)"; exit 1; }
    if diff <(cat "$base") <(referencia); then
        echo "OK: 1o turno no BI identico a referencia ($(basename "$base"))"
    else
        echo "ATENCAO: 1o turno no BI mudou desde $(basename "$base") (diff acima)"; exit 1
    fi
    my <<'SQL'
SELECT 'turno 2 no BI:', cargo, COUNT(*), SUM(votos) FROM shiftBI.resultados_candidato_municipio WHERE ano=2026 AND turno=2 GROUP BY cargo;
SQL
    exit 0
fi

ENSAIO=0; [ "${1:-}" = "--ensaio" ] && ENSAIO=1
if [ "$ENSAIO" = 0 ]; then
    [ -f .env.turno2 ] || { echo "falta .env.turno2 — o vigia_turno2 ainda nao viu o 2o turno publicado"; exit 1; }
    grep -q '^BI_TURNO=2' .env && { echo "o .env ja esta no 2o turno"; exit 1; }
    echo "Configuracao que sera aplicada:"; grep -v '^#' .env.turno2; echo
    read -r -p "Ligar a coleta do 2o turno? [s/N] " ok; [ "$ok" = "s" ] || { echo "cancelado"; exit 1; }
fi
T=$(date +%Y%m%d_%H%M)

# 1) Fonte do 1o turno: dump do MEGATRON com no maximo 2 h e legivel
dump="$BK/db/megatron-latest.dump"
idade=$(( $(date +%s) - $(stat -c %Y "$dump") ))
if [ "$idade" -gt 7200 ] || ! docker exec -i megatron-timescaledb-1 pg_restore -l < "$dump" >/dev/null 2>&1; then
    echo "ABORTADO: $dump com ${idade}s ou ilegivel — rode scripts/dump_db.sh e tente de novo"; exit 1
fi
log "dump do MEGATRON ok (${idade}s)"

# 2) Backup das linhas de presidente 2026 no BI + restauracao testada
B="$BK/bi_presidente2026_pre_turno2_$T.sql"
TAB="resultados_candidato resultados_candidato_municipio resultados_candidato_municipio_zona resultados_partido_municipio resultados_partido_municipio_zona detalhes_votacao_municipio detalhes_votacao_municipio_zona resultados_candidato_secao resultados_partido_secao detalhes_votacao_secao"
docker exec "$MYSQLC" sh -c "mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --set-gtid-purged=OFF --single-transaction --no-create-info --where=\"ano=2026 AND cargo='presidente'\" shiftBI $TAB" 2>/dev/null > "$B"
echo "DROP DATABASE IF EXISTS zz_rt_turno2; CREATE DATABASE zz_rt_turno2;" | my
for t in $TAB; do echo "CREATE TABLE zz_rt_turno2.$t LIKE shiftBI.$t;" | my; done
docker exec -i "$MYSQLC" sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" zz_rt_turno2' < "$B" 2>/dev/null
for t in $TAB; do
    a=$(echo "SELECT COUNT(*) FROM shiftBI.$t WHERE ano=2026 AND cargo='presidente'" | my)
    b=$(echo "SELECT COUNT(*) FROM zz_rt_turno2.$t" | my)
    [ "$a" = "$b" ] || { echo "ABORTADO: restauracao de $t nao bate ($a x $b)"; echo "DROP DATABASE zz_rt_turno2;" | my; exit 1; }
done
echo "DROP DATABASE zz_rt_turno2;" | my
log "backup do BI ok e restaurado em teste: $B"

# 3) Referencia do 1o turno
referencia > "$BK/bi_turno1_referencia-$T.txt"
log "referencia do 1o turno: $BK/bi_turno1_referencia-$T.txt"
[ "$ENSAIO" = 1 ] && { log "ENSAIO concluido: nada foi trocado"; exit 0; }

# 4) .env: guarda o atual e anexa o bloco do 2o turno
cp .env "$BK/env.pre-turno2-$T"
{ echo; cat .env.turno2; } >> .env
log ".env anterior em $BK/env.pre-turno2-$T"

# 5) Sobe os 4 servicos (bi_sync so quando ocioso, para nao cortar uma gravacao)
until docker exec megatron-redis-1 redis-cli get megatron:heartbeat:bi_sync | grep -q '"ocioso": true'; do
    log "aguardando o bi_sync terminar a rodada..."; sleep 30
done
docker compose -f "$COMPOSE" up -d $SERVICOS 2>&1 | grep -v obsolete
sleep 10
docker compose -f "$COMPOSE" ps --format '{{.Service}}|{{.Status}}' 2>/dev/null | grep -E "$(echo $SERVICOS | tr ' ' '|')"
log "2o TURNO LIGADO. Acompanhar: docker logs -f megatron-bi_sync-1 | scripts/ligar_turno2.sh --verificar"
