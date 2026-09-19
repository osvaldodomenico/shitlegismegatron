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
        pass "frontend servido pelo Caddy"
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

    # dado vivo: o snapshot precisa ser recente, nao fossil
    if curl -s --max-time 20 "https://$DOMINIO/resultados/sp/governador" -o /tmp/megatron-prod.json \
       && [ -s /tmp/megatron-prod.json ]; then
        if "$PY" - <<'EOF'
import json, sys
d = json.load(open("/tmp/megatron-prod.json"))
if "detail" in d:
    sys.exit(2)
sys.exit(0 if ("cand" in d and "pst" in d) else 1)
EOF
        then pass "/resultados entrega payload no formato TSE"
        else
            rc=$?
            [ "$rc" = "2" ] && fail "/resultados sem dados (collector nao publicou)" \
                            || fail "/resultados entrega payload em formato antigo"
        fi

        idade="$("$PY" - <<'EOF'
import json, sys
from datetime import datetime
d = json.load(open("/tmp/megatron-prod.json"))
try:
    dg = datetime.strptime(d.get("dg", ""), "%d/%m/%Y").date()
    print((datetime.now().date() - dg).days)
except Exception:
    print(-1)
EOF
)"
        if [ "$idade" = "0" ]; then
            pass "dado de producao e de hoje"
        elif [ "$idade" = "-1" ]; then
            fail "nao foi possivel ler a data do snapshot"
        else
            fail "dado de producao congelado ha ${idade} dia(s) — collector parado"
        fi
    else
        fail "/resultados nao respondeu"
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
