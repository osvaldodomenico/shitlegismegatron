#!/usr/bin/env bash
# VOLTA a coleta ao 1o turno: restaura o .env de antes do ligar_turno2.sh e sobe
# os 4 servicos de novo. NAO apaga o turno 2 do BI (comando ao final, se quiser).
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
SERVICOS="collector_municipios collector_urnas collector_bu bi_sync"
ant=$(ls -t backups/env.pre-turno2-* 2>/dev/null | head -1)
[ -n "$ant" ] || { echo "nao ha .env salvo pelo ligar_turno2.sh"; exit 1; }
read -r -p "Restaurar $ant e voltar ao 1o turno? [s/N] " ok; [ "$ok" = "s" ] || { echo "cancelado"; exit 1; }
cp .env "backups/env.turno2-desligado-$(date +%Y%m%d_%H%M)"
cp "$ant" .env
until docker exec megatron-redis-1 redis-cli get megatron:heartbeat:bi_sync | grep -q '"ocioso": true'; do sleep 30; done
docker compose -f docker-compose.bi.yml up -d $SERVICOS 2>&1 | grep -v obsolete
echo "De volta ao 1o turno. Para tirar o 2o turno do BI (opcional), no MySQL shiftBI:"
echo "  DELETE FROM <tabela> WHERE ano=2026 AND turno=2   (resultados_*_municipio[_zona], *_secao, detalhes_*)"
