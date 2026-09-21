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

DOMINIO="${MEGATRON_DOMAIN:-megatron.shiftworks.app.br}"
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
URL_REAL="https://resultados.tse.jus.br/oficial/ele2022/544/dados-simplificados/br/br-c0001-e000544-r.json"
code="$(curl -s -o /tmp/megatron-tse-ref.json -w '%{http_code}' -A 'Megatron/1.0' \
    -e 'https://resultados.tse.jus.br/' --max-time 20 "$URL_REAL")"
if [ "$code" = "200" ]; then
    pass "esquema dados-simplificados/-r.json responde 200 na CDN do TSE"
else
    fail "esquema de URL do collector nao responde na CDN (HTTP $code)"
fi

# 2.2 o payload real satisfaz a validacao do fetcher
if [ -s /tmp/megatron-tse-ref.json ]; then
    if "$PY" - <<'EOF'
import json, sys
sys.path.insert(0, "collector")
from fetcher import REQUIRED_KEYS
d = json.load(open("/tmp/megatron-tse-ref.json"))
sys.exit(0 if REQUIRED_KEYS.issubset(d.keys()) else 1)
EOF
    then pass "payload real do TSE passa na validacao do fetcher"
    else fail "fetcher rejeitaria o payload real do TSE (REQUIRED_KEYS nao batem)"
    fi

    # 2.3 o simulador emite o MESMO formato que o TSE real
    if "$PY" - <<'EOF'
import json, sys
sys.path.insert(0, "simulator")
from generator import gerar_resultado
real = json.load(open("/tmp/megatron-tse-ref.json"))
sim = gerar_resultado("br", "0001")
if set(sim) - set(real):
    sys.exit(1)
if set(sim["cand"][0]) != set(real["cand"][0]):
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

    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMINIO/health")"
    [ "$code" = "200" ] && pass "API /health responde 200" || fail "API /health retornou $code"

    html="$(curl -s --max-time 20 "https://$DOMINIO/")"
    if printf '%s' "$html" | grep -q 'id="root"'; then
        pass "frontend servido pelo proxy reverso"
    else
        fail "frontend nao respondeu HTML esperado"
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
    curl -s --max-time 20 "https://$DOMINIO/corridas" -o /tmp/megatron-corridas.json
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

    if curl -s --max-time 30 "https://$DOMINIO/resultados/$PRIMEIRA" -o /tmp/megatron-prod.json \
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
        if curl -s --max-time 20 "https://$DOMINIO/health" -o /tmp/megatron-health.json \
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

    if curl -s --max-time 30 "https://$DOMINIO/candidatos/$CORRIDA" -o /tmp/megatron-cands.json \
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

    if curl -s --max-time 20 "https://$DOMINIO/selecao/$CORRIDA" -o /tmp/megatron-sel.json \
       && "$PY" -c "import json,sys; d=json.load(open('/tmp/megatron-sel.json')); sys.exit(0 if isinstance(d.get('sqcands'),list) and d.get('maximo')==5 else 1)"; then
        pass "/selecao expoe a escolha e o limite de 5"
    else
        fail "/selecao nao respondeu como esperado"
    fi

    # O ganho do filtro e a razao de ele existir: se o recorte parar de
    # funcionar, o payload volta a ~240 KB e a tela trava no dia da apuracao.
    cheio="$(curl -s --max-time 40 -o /dev/null -w '%{size_download}' "https://$DOMINIO/resultados/$CORRIDA")"
    filtrado="$(curl -s --max-time 40 -o /dev/null -w '%{size_download}' "https://$DOMINIO/resultados/$CORRIDA?selecionados=true")"
    if [ "${cheio:-0}" -gt 0 ] && [ "${filtrado:-0}" -gt 0 ]; then
        if [ "$filtrado" -lt "$((cheio / 10))" ]; then
            pass "filtro no servidor reduz o payload ($((cheio / 1024)) KB -> $((filtrado / 1024)) KB)"
        else
            fail "filtro no servidor nao reduziu o payload ($cheio -> $filtrado bytes)"
        fi
    else
        fail "nao foi possivel medir o ganho do filtro"
    fi

    # Quociente e linha de corte: indicador que decide leitura de eleicao.
    # Se o calculo quebrar, a tela passa a afirmar quem se elege com numero
    # errado — pior do que nao mostrar nada.
    if curl -s --max-time 40 "https://$DOMINIO/resultados/$CORRIDA?selecionados=true" -o /tmp/megatron-ind.json \
       && [ -s /tmp/megatron-ind.json ]; then
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
        fail "nao foi possivel ler os indicadores de apuracao"
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
