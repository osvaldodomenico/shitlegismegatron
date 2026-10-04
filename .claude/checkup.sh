#!/usr/bin/env bash
# MEGATRON — checkup de release (read-only).
#
# Valida FUNCIONALMENTE o que foi entregue e imprime PASS/FAIL.
# Sai com codigo != 0 se qualquer item falhar.
#
#   ./.claude/checkup.sh          # local + producao
#   SKIP_PROD=1 ./.claude/checkup.sh   # so local
#
# Nao escreve nada em producao e nao altera o repositorio.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# Producao rodou a migracao de dominio para megatron.shiftlegis.com.br em 03/10/2026:
# o {DOM_ANTIGO} responde 301 de redirecionamento. Sem esta troca o checkup
# acusaria falha de API e bundle em uma producao saudavel.
DOMINIO="${MEGATRON_DOMAIN:-megatron.shiftlegis.com.br}"
VENV="${MEGATRON_CHECKUP_VENV:-/tmp/megatron-checkup-venv}"

FALHAS=0
pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FALHAS=$((FALHAS + 1)); }
secao() { printf '\n=== %s ===\n' "$1"; }

# ---------------------------------------------------------------- venv
if [ ! -x "$VENV/bin/python" ]; then
    echo "Preparando venv de teste em $VENV ..."
    python3 -m venv "$VENV" >/dev/null 2>&1
    "$VENV/bin/pip" install -q pytest pytest-asyncio respx httpx fastapi redis asyncpg >/dev/null 2>&1
fi
PY="$VENV/bin/python"

# ------------------------------------------------------- 1. testes unitarios
# Cada servico roda isolado: collector/ e simulator/ tem ambos um main.py,
# e rodar da raiz colide no import.
secao "Testes unitarios"
for svc in collector simulator api; do
    saida="$(cd "$svc" && REDIS_URL=redis://localhost:6379 "$PY" -m pytest tests -q 2>&1)"
    if printf '%s' "$saida" | grep -qE '[0-9]+ passed' && ! printf '%s' "$saida" | grep -qE 'failed|error'; then
        pass "$svc — $(printf '%s' "$saida" | grep -oE '[0-9]+ passed' | head -1)"
    else
        fail "$svc — pytest nao passou"
        printf '%s\n' "$saida" | tail -5
    fi
done

saida="$(cd frontend && npm test 2>&1)"
if printf '%s' "$saida" | grep -q 'Tests .*passed' && ! printf '%s' "$saida" | grep -q 'failed'; then
    pass "frontend — $(printf '%s' "$saida" | grep -oE 'Tests +[0-9]+ passed' | head -1)"
else
    fail "frontend — vitest nao passou"
fi

# ------------------------------------------------- 2. schema TSE (contrato)
secao "Contrato com o TSE"

# 2.1 o esquema de URL usado pelo collector ainda responde 200 na CDN real
URL_REAL="https://resultados.tse.jus.br/oficial/ele2026/6257/dados/br/br-c0001-e006257-u.json"
code="$(curl -s -o /tmp/megatron-tse-ref.json -w '%{http_code}' -A 'Megatron/1.0' \
    -e 'https://resultados.tse.jus.br/' --max-time 20 "$URL_REAL")"
if [ "$code" = "200" ]; then
    pass "esquema dados/-u.json responde 200 na CDN do TSE"
else
    fail "esquema de URL do collector nao responde na CDN (HTTP $code) — ver tse_nested e TSE_PATH_DADOS"
fi

# 2.2 o payload real satisfaz a validacao do fetcher
if [ -s /tmp/megatron-tse-ref.json ]; then
    if "$PY" - <<'EOF'
import json, sys
sys.path.insert(0, "collector")
from fetcher import REQUIRED_KEYS
from tse_nested import achatar
d = achatar(json.load(open("/tmp/megatron-tse-ref.json")))
sys.exit(0 if REQUIRED_KEYS.issubset(d.keys()) else 1)
EOF
    then pass "payload real do TSE passa na validacao do fetcher"
    else fail "fetcher rejeitaria o payload real do TSE (REQUIRED_KEYS nao batem)"
    fi

    # 2.3 o simulador emite o MESMO formato que o TSE real (contrato plano)
    if "$PY" - <<'EOF'
import json, sys
sys.path.insert(0, "simulator")
sys.path.insert(0, "collector")
from generator import gerar_resultado
from tse_nested import achatar
real = achatar(json.load(open("/tmp/megatron-tse-ref.json")))
sim = gerar_resultado("br", "0001")
# contrato plano: ambos tem pst/cand/hg no topo; cand tem cc/vap/sqcand
if not {"pst","cand","hg"}.issubset(sim.keys()):
    sys.exit(1)
if not {"pst","cand","hg"}.issubset(real.keys()):
    sys.exit(1)
if not sim.get("cand") or not real.get("cand"):
    sys.exit(1)
# chaves essenciais do candidato (sem exigir igualdade exata: real tem ccd/nmu/pvapn extras)
essenciais = {"sqcand","n","nm","cc","vap","pvap","st","dvt"}
if not essenciais.issubset(set(sim["cand"][0].keys())):
    sys.exit(1)
if not essenciais.issubset(set(real["cand"][0].keys())):
    sys.exit(1)
if "%" in sim["pst"] or "," not in sim["pst"]:
    sys.exit(1)
sys.exit(0)
EOF
    then pass "simulador emite o mesmo formato do TSE real (chaves e decimais)"
    else fail "simulador divergiu do formato do TSE real"
    fi
fi

# ------------------------------------------------------- 3. build frontend
secao "Build do frontend"
if (cd frontend && npm run build >/tmp/megatron-build.log 2>&1); then
    bundle="$(ls -S frontend/dist/assets/*.js 2>/dev/null | head -1)"
    if [ -n "$bundle" ] && grep -q 'createRoot\|MEGATRON' "$bundle"; then
        pass "bundle gerado com a aplicacao React ($(du -h "$bundle" | cut -f1))"
    else
        fail "bundle gerado SEM codigo de app (src/main.jsx vazio?)"
    fi
    if ls frontend/dist/assets/*.css >/dev/null 2>&1; then
        pass "CSS do Tailwind gerado"
    else
        fail "nenhum CSS gerado — Tailwind nao entrou no build"
    fi
else
    fail "npm run build falhou"; tail -5 /tmp/megatron-build.log
fi

# ------------------------------------------------------------ 4. producao
if [ "${SKIP_PROD:-0}" = "1" ]; then
    secao "Producao (pulado: SKIP_PROD=1)"
else
    secao "Producao — https://$DOMINIO"

    code="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMINIO/health")"
    [ "$code" = "200" ] && pass "API /health responde 200" || fail "API /health retornou $code"

    html="$(curl -sL --max-time 20 "https://$DOMINIO/")"
    if printf '%s' "$html" | grep -q 'id="root"'; then
        pass "frontend servido pelo proxy reverso"
    else
        fail "frontend nao respondeu HTML esperado"
    fi

    # /painel (telao 1920x1080) e /dashboard (vertical 1080x1920) sao rotas so
    # do SPA: precisam cair no try_files do nginx e servir o MESMO bundle da
    # raiz — se o Traefik mandar para a API vira 404/405, sem fallback vira 404.
    for rota in /painel /dashboard /apuracaogeral; do
        tela="$(curl -sL --max-time 20 "https://$DOMINIO$rota")"
        if printf '%s' "$tela" | grep -q 'id="root"' \
           && [ "$(printf '%s' "$tela" | grep -oE '/assets/[^"]+\.js' | head -1)" = "$(printf '%s' "$html" | grep -oE '/assets/[^"]+\.js' | head -1)" ]; then
            pass "$rota servido pelo SPA com o mesmo bundle da raiz"
        else
            fail "$rota nao serve a aplicacao (rota do telao quebrada)"
        fi
    done

    # Coletor por municipio: heartbeat no Redis (expira em 3 ciclos) e as
    # 645 cidades de SP presentes em votos_municipio para cada cargo.
    # Niveis: municipio (645 cidades) e zona (779 pares zona x cidade), x 4 cargos.
    mun="$(ssh -o ConnectTimeout=10 vps2 'docker exec megatron-redis-1 redis-cli get megatron:heartbeat:municipios; docker exec megatron-timescaledb-1 psql -U megatron -d megatron -tAc "select nivel || chr(61) || count(distinct cargo) || chr(120) || min(c) from (select nivel, cargo, count(*) c from votos_municipio group by 1,2) t group by nivel order by nivel"' 2>/dev/null)"
    if printf '%s' "$mun" | head -1 | grep -q '"ts"' \
       && printf '%s' "$mun" | grep -q '^municipio=4x645$' \
       && printf '%s' "$mun" | grep -q '^zona=4x779$'; then
        pass "coletor de municipios vivo — 645 cidades e 779 zonas x 4 cargos no banco"
    else
        fail "coletor de municipios parado ou incompleto ($(printf '%s' "$mun" | tail -2 | tr '\n' ' '))"
    fi

    asset="$(printf '%s' "$html" | grep -oE '/assets/[^"]+\.js' | head -1)"
    if [ -n "$asset" ]; then
        bytes="$(curl -s -o /tmp/megatron-prod.js -w '%{size_download}' --max-time 20 "https://$DOMINIO$asset")"
        if [ "$bytes" -gt 100000 ] && grep -q 'createRoot\|useState' /tmp/megatron-prod.js; then
            pass "bundle em producao contem a aplicacao (${bytes} bytes)"
        else
            fail "bundle em producao esta vazio de app (${bytes} bytes) — pagina em branco"
        fi
    else
        fail "HTML de producao nao referencia bundle JS"
    fi

    # A corrida testada sai de /corridas, e nao cravada: assim o checkup
    # acompanha mudanca de escopo sozinho, em vez de falhar por estar olhando
    # para uma corrida que saiu do .env.
    curl -sL --max-time 20 "https://$DOMINIO/corridas" -o /tmp/megatron-corridas.json
    PRIMEIRA="$("$PY" - <<'EOF'
import json
try:
    d = json.load(open("/tmp/megatron-corridas.json"))
except Exception:
    raise SystemExit
com_dado = [c for c in (d.get("corridas") or []) if c.get("com_dado")]
if com_dado:
    print(f"{com_dado[0]['uf']}/{com_dado[0]['cargo']}")
EOF
)"
    if [ -z "$PRIMEIRA" ]; then
        fail "/corridas nao listou nenhuma corrida com dado"
        PRIMEIRA="sp/dep_federal"
    fi

    if curl -sL --max-time 30 "https://$DOMINIO/resultados/$PRIMEIRA" -o /tmp/megatron-prod.json \
       && [ -s /tmp/megatron-prod.json ]; then
        if "$PY" - <<'EOF'
import json, sys
d = json.load(open("/tmp/megatron-prod.json"))
if "detail" in d:
    sys.exit(2)
sys.exit(0 if ("cand" in d and "pst" in d) else 1)
EOF
        then pass "/resultados entrega payload no formato TSE ($PRIMEIRA)"
        else
            rc=$?
            [ "$rc" = "2" ] && fail "/resultados sem dados (collector nao publicou)" \
                            || fail "/resultados entrega payload em formato antigo"
        fi

        # Liveness do collector, NAO a data dentro do boletim. O fetcher so
        # publica quando o payload muda, entao "dado antigo" pode ser silencio
        # legitimo — durante um replay de eleicao passada, sempre e. O sinal
        # honesto e o heartbeat que o collector grava a cada ciclo.
        if curl -sL --max-time 20 "https://$DOMINIO/health" -o /tmp/megatron-health.json \
           && "$PY" - <<'EOF'
import json, sys
h = json.load(open("/tmp/megatron-health.json"))
c = h.get("coletor") or {}
if c.get("estado") != "ok":
    print(f"coletor em '{c.get('estado')}': {c.get('detalhe', '')}", file=sys.stderr)
    sys.exit(1)
if (c.get("falhas_ultimo_ciclo") or 0) >= (c.get("tarefas") or 1):
    print("todas as URLs falharam no ultimo ciclo", file=sys.stderr)
    sys.exit(1)
corr = h.get("corridas") or {}
if not corr.get("com_dado"):
    print("nenhuma corrida com boletim", file=sys.stderr)
    sys.exit(1)
print(f"{corr['com_dado']}/{corr['configuradas']} corridas com dado, "
      f"heartbeat {c['idade_segundos']}s")
EOF
        then pass "collector coletando (heartbeat fresco)"
        else fail "collector parado ou sem coletar — ver /health"
        fi
    else
        fail "/resultados nao respondeu"
    fi

    # ---- acompanhamento de candidatos (filtro no servidor) ----
    secao "Acompanhamento — ate 5 candidatos"

    CORRIDA="${MEGATRON_CORRIDA_GRANDE:-sp/dep_federal}"

    if curl -sL --max-time 30 "https://$DOMINIO/candidatos/$CORRIDA" -o /tmp/megatron-cands.json \
       && [ -s /tmp/megatron-cands.json ]; then
        if "$PY" - <<'EOF'
import json, sys
d = json.load(open("/tmp/megatron-cands.json"))
c = d.get("candidatos") or []
# lista do seletor: so os campos leves, senao voltam os ~240 KB do payload
if not c or set(c[0]) != {"sqcand", "nm", "cc", "n"}:
    sys.exit(1)
sys.exit(0 if d.get("total") == len(c) else 1)
EOF
        then pass "/candidatos entrega lista enxuta para o seletor"
        else fail "/candidatos com formato inesperado"
        fi
    else
        fail "/candidatos nao respondeu em $CORRIDA"
    fi

    # Perfil "geral" (/apuracaogeral) e independente do padrao: responde com o
    # proprio nome e nunca com a lista do painel.
    if curl -sL --max-time 20 "https://$DOMINIO/selecao/$CORRIDA?perfil=geral" -o /tmp/megatron-sel-geral.json \
       && "$PY" -c "import json,sys; d=json.load(open('/tmp/megatron-sel-geral.json')); sys.exit(0 if d.get('perfil')=='geral' and isinstance(d.get('sqcands'),list) else 1)"; then
        pass "/selecao?perfil=geral responde com lista propria"
    else
        fail "/selecao?perfil=geral nao respondeu como esperado"
    fi

    if curl -sL --max-time 20 "https://$DOMINIO/selecao/$CORRIDA" -o /tmp/megatron-sel.json \
       && "$PY" -c "import json,sys; d=json.load(open('/tmp/megatron-sel.json')); m=d.get('maximo'); sys.exit(0 if isinstance(d.get('sqcands'),list) and isinstance(m,int) and m>=5 else 1)"; then
        pass "/selecao expoe a escolha e o limite ($("$PY" -c "import json; print(json.load(open('/tmp/megatron-sel.json'))['maximo'])"))"
    else
        fail "/selecao nao respondeu como esperado"
    fi

    # ---- filtro no servidor: mede o ganho sobre uma escolha REAL ----
    # A selecao salva em producao pode ser de uma eleicao anterior (os
    # `sqcand` de 2022 nao existem no payload de 2026). Nesse caso o
    # recorte devolve `cand: []` e a medicao de bytes passaria a toa por
    # medir "vazio", nao "filtrado". O checkup grava 2 candidatos que
    # EXISTEM no payload atual, mede, e restaura a selecao anterior.
    curl -sL --max-time 40 "https://$DOMINIO/resultados/$CORRIDA" -o /tmp/megatron-full.json || true
    ESCOLHA_TESTE="$("$PY" -c "
import json
d = json.load(open('/tmp/megatron-full.json'))
print(','.join(str(c.get('sqcand')) for c in (d.get('cand') or [])[:2]))
" 2>/dev/null || echo "")"
    printf '%s' "$ESCOLHA_TESTE" | tr ',' ' ' > /tmp/megatron-escolha.txt
    ESCOLHA_ORIGINAL="$("$PY" -c "
import json
print(','.join(json.load(open('/tmp/megatron-sel.json')).get('sqcands') or []))
" 2>/dev/null || echo "")"
    if [ -n "$ESCOLHA_TESTE" ]; then
        ESCOLHA_JSON="$("$PY" -c "
import json, sys
print(json.dumps([x for x in sys.argv[1].split(',') if x]))
" "$ESCOLHA_TESTE" 2>/dev/null || echo "[]")"
        curl -sL --max-time 20 -X PUT "https://$DOMINIO/selecao/$CORRIDA" \
            -H 'Content-Type: application/json' -d "{\"sqcands\": $ESCOLHA_JSON}" \
            -o /dev/null || true
    fi

    # O ganho do filtro e a razao de ele existir: se o recorte parar de
    # funcionar, o payload volta a ~230 KB e a tela trava no dia da apuracao.
    cheio="$(curl -sL --max-time 40 -o /dev/null -w '%{size_download}' "https://$DOMINIO/resultados/$CORRIDA")"
    filtrado="$(curl -sL --max-time 40 -o /dev/null -w '%{size_download}' "https://$DOMINIO/resultados/$CORRIDA?selecionados=true")"
    if [ "${cheio:-0}" -gt 0 ] && [ "${filtrado:-0}" -gt 0 ]; then
        if [ "$filtrado" -lt "$((cheio / 10))" ]; then
            pass "filtro no servidor reduz o payload ($((cheio / 1024)) KB -> $((filtrado / 1024)) KB)"
        else
            fail "filtro no servidor nao reduziu o payload ($cheio -> $filtrado bytes)"
        fi
    else
        fail "nao foi possivel medir o ganho do filtro"
    fi

    # ---- indicadores de apuracao: a lei so tem valor com votos ----
    # Antes da urna (vv=0, pst=0,00) `apuracao.calcular` devolve {} de
    # proposito: quociente com zero votos nao divide. Exigir indicador
    # nesse estagio reprovaria uma producao saudavel na vespera da
    # eleicao — exatamente o dia em que o checkup precisa passar.
    # Antes da urna exigimos o CONTRATO (payload achatado, filtro
    # devolvendo so os acompanhados, foto montada). Depois da urna
    # exigimos o calculo legal conferido contra o art. 106.
curl -sL --max-time 40 "https://$DOMINIO/resultados/$CORRIDA?selecionados=true" -o /tmp/megatron-ind.json || true
    APURADO="$("$PY" -c "
import json
d = json.load(open('/tmp/megatron-ind.json'))
vv = int(str(d.get('vv') or '0').replace('.', '').replace(',', '') or 0)
print('sim' if vv > 0 else 'nao')
" 2>/dev/null || echo nao)"

    if [ -s /tmp/megatron-ind.json ]; then
        if [ "$APURADO" = "sim" ]; then
            if "$PY" - <<'EOF'
import json, sys
d = json.load(open("/tmp/megatron-ind.json"))
i = d.get("indicadores") or {}
qe, vagas, vv = i.get("quociente_eleitoral"), i.get("vagas"), i.get("votos_validos")
if not (qe and vagas and vv):
    sys.exit(1)
# art. 106 do Codigo Eleitoral: despreza fracao <= 0,5
bruto = vv / vagas
esperado = int(bruto) + (1 if (bruto - int(bruto)) > 0.5 else 0)
if qe != esperado:
    sys.exit(1)
if i.get("barreira_individual") != int(qe * 0.10):
    sys.exit(1)
# todo acompanhado precisa trazer o bloco de indicadores e a foto
for c in d.get("cand") or []:
    if not c.get("ind") or not c.get("foto"):
        sys.exit(1)
sys.exit(0)
EOF
            then pass "quociente, barreira e linha de corte conferem com a lei"
            else fail "indicadores de apuracao ausentes ou divergentes"
            fi
        else
            if "$PY" - <<'EOF'
import json, sys
d = json.load(open("/tmp/megatron-ind.json"))
# contrato do payload achatado: chaves do TSE no topo
for k in ("pst", "vv", "hg", "cand", "ele"):
    if k not in d:
        sys.exit(1)
# antes da urna nao pode haver indicador inventado
if d.get("indicadores"):
    sys.exit(1)
# filtro precisa devolver SO os acompanhados, com foto montada
escolhidos = {str(x) for x in open("/tmp/megatron-escolha.txt").read().split() if x}
cands = d.get("cand") or []
if not cands:
    sys.exit(1)
if {str(c.get("sqcand")) for c in cands} != escolhidos:
    sys.exit(1)
for c in cands:
    if not str(c.get("foto") or "").endswith(".jpeg"):
        sys.exit(1)
sys.exit(0)
EOF
            then pass "pre-urna: payload achatado, filtro so dos acompanhados, sem indicador inventado"
            else fail "contrato do payload falhou no pre-urna"
            fi
        fi
    else
        fail "nao foi possivel ler os indicadores de apuracao"
    fi

    # restaura a selecao que estava salva antes do teste
    if [ -n "$ESCOLHA_ORIGINAL" ]; then
        ORIG_JSON="$("$PY" -c "
import json, sys
print(json.dumps([x for x in sys.argv[1].split(',') if x]))
" "$ESCOLHA_ORIGINAL" 2>/dev/null || echo "[]")"
        curl -sL --max-time 20 -X PUT "https://$DOMINIO/selecao/$CORRIDA" \
            -H 'Content-Type: application/json' -d "{\"sqcands\": $ORIG_JSON}" \
            -o /dev/null || true
    else
        curl -sL --max-time 20 -X PUT "https://$DOMINIO/selecao/$CORRIDA" \
            -H 'Content-Type: application/json' -d '{"sqcands": []}' \
            -o /dev/null || true
    fi
fi

# -------------------------------------------------------------- resultado
printf '\n'
if [ "$FALHAS" -eq 0 ]; then
    printf '\033[32mCHECKUP: OK — 0 FAIL\033[0m\n'
    exit 0
fi
printf '\033[31mCHECKUP: %d FAIL\033[0m\n' "$FALHAS"
exit 1
