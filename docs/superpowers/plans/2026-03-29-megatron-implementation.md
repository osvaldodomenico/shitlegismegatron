# MEGATRON Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o sistema MEGATRON — ingestão, processamento e exibição em tempo real de dados de apuração eleitoral brasileira (TSE 2026), com simulador local para desenvolvimento.

**Architecture:** Coletor Python/httpx busca endpoints TSE, publica mudanças em Redis Streams via diff-hash. API FastAPI consome o stream, persiste no TimescaleDB e faz broadcast via WebSocket. Frontend Vite/React 18 exibe dashboard público dark-mode com gráficos em tempo real.

**Tech Stack:** Python 3.11, FastAPI, httpx, APScheduler, Redis Streams, TimescaleDB (PostgreSQL 15), Vite, React 18, Tailwind CSS, recharts, Docker Compose, pytest, vitest

**Spec:** `docs/superpowers/specs/2026-03-29-megatron-design.md`

---

## File Map

```
megatron/
├── docker-compose.yml
├── .env.example
├── .env                          # gitignored
├── .gitignore
│
├── collector/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── tse_urls.py               # URL templates + constantes
│   ├── fetcher.py                # fetch_if_changed() com hash MD5
│   ├── publisher.py              # publish() para Redis Stream
│   ├── main.py                   # APScheduler entry point
│   └── tests/
│       ├── test_tse_urls.py
│       ├── test_fetcher.py
│       └── test_publisher.py
│
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── generator.py              # gerar_resultado() progressivo
│   ├── main.py                   # FastAPI imitando CDN TSE
│   └── fixtures/
│       ├── candidatos.json
│       └── municipios.json
│
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── db.py                     # conexão AsyncPG + seed schema
│   ├── ws_manager.py             # ConnectionManager (rooms)
│   ├── consumer.py               # xread → broadcast + persist
│   ├── main.py                   # FastAPI app + startup
│   ├── routes/
│   │   ├── resultados.py         # GET /resultados/{uf}/{cargo}
│   │   ├── historico.py          # GET /historico/{uf}/{cargo}
│   │   └── health.py             # GET /health
│   └── tests/
│       ├── conftest.py           # fixtures: app, fake redis, fake db
│       ├── test_ws_manager.py
│       ├── test_consumer.py
│       └── test_routes.py
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── hooks/
│       │   └── useElectionSocket.js  # WS + backoff exponencial
│       ├── components/
│       │   ├── Header.jsx            # seletor UF/cargo + status
│       │   ├── StatusBanner.jsx      # 🟢/🔴/🟡 conexão
│       │   ├── ProgressBar.jsx       # % seções apuradas
│       │   ├── CandidatosTable.jsx   # tabela com barras inline
│       │   ├── ResultadoChart.jsx    # BarChart horizontal recharts
│       │   └── HistoricoChart.jsx    # LineChart temporal recharts
│       └── test/
│           ├── useElectionSocket.test.js
│           └── components.test.jsx
│
└── scripts/
    ├── seed_db.py                # cria extensão + hypertable + índices
    └── test_endpoints.py         # smoke test dos endpoints TSE
```

---

## Chunk 1: Infraestrutura Base

### Task 1: Scaffold do projeto

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`

- [ ] **Step 1: Criar .gitignore**

```
.env
__pycache__/
*.pyc
*.pyo
node_modules/
dist/
.pytest_cache/
.coverage
*.egg-info/
```

Salvar em `megatron/.gitignore`.

- [ ] **Step 2: Criar .env.example**

```env
# TSE / Simulador
# Em dev: TSE_BASE_URL=http://simulator:8001/oficial/ele2026
TSE_BASE_URL=https://resultados.tse.jus.br/oficial/ele2026
POLL_INTERVAL_SECONDS=60

# Eleição alvo 2026
# Buscar em: https://resultados.tse.jus.br/oficial/ele2026/ele.json
# após TSE publicar os códigos (~semanas antes da eleição)
ELE_1T=TBD
ELE_2T=TBD

# Monitoramento (listas separadas por vírgula)
UFS=sp,rj,mg,rs,ba,pr,pe,ce,pa,sc,br
CARGOS=presidente,governador

# Infra
REDIS_URL=redis://redis:6379
POSTGRES_USER=megatron
POSTGRES_PASSWORD=change-me-in-production
POSTGRES_DB=megatron

# Simulador (dev)
DURACAO_SIMULACAO=3600
```

Salvar em `megatron/.env.example`.

- [ ] **Step 3: Copiar .env para dev**

```bash
cd ~/Documents/Projetos/megatron
cp .env.example .env
# Editar .env: ajustar POSTGRES_PASSWORD e ELE_1T se necessário
```

- [ ] **Step 4: Criar frontend/postcss.config.js**

```javascript
// Necessário para Tailwind CSS v3 funcionar com PostCSS
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

Salvar em `frontend/postcss.config.js`.

- [ ] **Step 5: Criar docker-compose.yml**

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports: ["5432:5432"]
    volumes: ["pg_data:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 10

  simulator:
    build: ./simulator
    ports: ["8001:8001"]
    environment:
      DURACAO_SIMULACAO: ${DURACAO_SIMULACAO:-3600}
    profiles: ["dev"]

  collector:
    build: ./collector
    environment:
      REDIS_URL: ${REDIS_URL}
      POLL_INTERVAL_SECONDS: ${POLL_INTERVAL_SECONDS:-60}
      TSE_BASE_URL: ${TSE_BASE_URL}
      ELE_1T: ${ELE_1T}
      UFS: ${UFS}
      CARGOS: ${CARGOS}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  api:
    build: ./api
    ports: ["8000:8000"]
    environment:
      REDIS_URL: ${REDIS_URL}
      POSTGRES_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@timescaledb/${POSTGRES_DB}
    depends_on:
      redis:
        condition: service_healthy
      timescaledb:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      VITE_API_URL: http://localhost:8000
      VITE_WS_URL: ws://localhost:8000
    depends_on:
      - api

volumes:
  redis_data:
  pg_data:
```

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add .gitignore .env.example docker-compose.yml frontend/postcss.config.js
git commit -m "chore(infra): scaffold project files, docker-compose, postcss config"
```

---

### Task 2: Script seed_db.py

**Files:**
- Create: `scripts/seed_db.py`
- Create: `scripts/tests/test_seed_db.py`

- [ ] **Step 1: Escrever teste do seed_db**

Criar `scripts/tests/test_seed_db.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch, call

def test_seed_sai_sem_postgres_url(monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        import seed_db
        seed_db.seed()
    assert exc.value.code == 1

def test_seed_chama_create_extension(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://fake:fake@localhost/fake")
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    with patch("psycopg2.connect", return_value=mock_conn):
        import importlib, seed_db
        importlib.reload(seed_db)
        seed_db.seed()
    sqls = [c.args[0] for c in mock_cur.execute.call_args_list]
    assert any("timescaledb" in s for s in sqls)
    assert any("snapshots" in s for s in sqls)
    assert any("create_hypertable" in s for s in sqls)
```

- [ ] **Step 2: Executar teste — deve falhar**

```bash
cd ~/Documents/Projetos/megatron
pip install psycopg2-binary pytest -q
python3 -m pytest scripts/tests/test_seed_db.py -v
```

Esperado: `ModuleNotFoundError: No module named 'seed_db'`

- [ ] **Step 3: Criar scripts/seed_db.py**

```python
#!/usr/bin/env python3
"""
Inicializa o schema do TimescaleDB (extensão + hypertable + índices).
Executar uma vez antes do primeiro uso da API.
"""
import os
import sys
import psycopg2

def seed():
    url = os.environ.get("POSTGRES_URL")
    if not url:
        print("[seed_db] POSTGRES_URL não definido", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    print("[seed_db] Criando extensão timescaledb...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    print("[seed_db] Criando tabela snapshots...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            time        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            uf          TEXT            NOT NULL,
            cargo       TEXT            NOT NULL,
            pst_pct     NUMERIC(5,2),
            payload     JSONB
        );
    """)

    print("[seed_db] Criando hypertable...")
    cur.execute("""
        SELECT create_hypertable('snapshots', 'time', if_not_exists => TRUE);
    """)

    print("[seed_db] Criando índice (uf, cargo, time DESC)...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_uf_cargo_time
        ON snapshots (uf, cargo, time DESC);
    """)

    cur.close()
    conn.close()
    print("[seed_db] Schema inicializado com sucesso.")

if __name__ == "__main__":
    seed()
```

- [ ] **Step 4: Executar testes — deve passar**

```bash
python3 -m pytest scripts/tests/test_seed_db.py -v
```

Esperado: 2 testes `PASSED`.

- [ ] **Step 5: Testar localmente (requer timescaledb rodando)**

```bash
cd ~/Documents/Projetos/megatron
docker compose up -d timescaledb
docker compose up --wait timescaledb  # bloqueia até healthcheck passar
POSTGRES_URL="postgresql://megatron:change-me-in-production@localhost:5432/megatron" \
  python3 scripts/seed_db.py
```

Resultado esperado:
```
[seed_db] Criando extensão timescaledb...
[seed_db] Criando tabela snapshots...
[seed_db] Criando hypertable...
[seed_db] Criando índice (uf, cargo, time DESC)...
[seed_db] Schema inicializado com sucesso.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_db.py scripts/tests/
git commit -m "feat(scripts): seed_db creates TimescaleDB schema and hypertable, with tests"
```

---

## Chunk 2: Simulator

### Task 3: Gerador de dados sintéticos

**Files:**
- Create: `simulator/generator.py`
- Create: `simulator/fixtures/candidatos.json`
- Create: `simulator/fixtures/municipios.json`
- Create: `simulator/tests/__init__.py`
- Create: `simulator/tests/test_generator.py`

- [ ] **Step 1: Criar fixtures/candidatos.json**

```json
[
  {"sqcand": "001", "nm": "AURORA SILVA",   "sg": "PARTIDO-A", "n": "10"},
  {"sqcand": "002", "nm": "BRUNO SANTOS",   "sg": "PARTIDO-B", "n": "13"},
  {"sqcand": "003", "nm": "CARLA MENDES",   "sg": "PARTIDO-C", "n": "20"},
  {"sqcand": "004", "nm": "DIEGO FERREIRA", "sg": "PARTIDO-D", "n": "45"}
]
```

Salvar em `simulator/fixtures/candidatos.json`.

- [ ] **Step 2: Criar fixtures/municipios.json**

```json
[
  {"cd": "sp", "nm": "SÃO PAULO (SIMULADO)"},
  {"cd": "rj", "nm": "RIO DE JANEIRO (SIMULADO)"},
  {"cd": "mg", "nm": "MINAS GERAIS (SIMULADO)"}
]
```

Salvar em `simulator/fixtures/municipios.json`.

- [ ] **Step 3: Criar simulator/generator.py**

```python
"""
Gera resultados eleitorais sintéticos com progressão 0% → 100%.
DURACAO_SIMULACAO (segundos) controla a velocidade da simulação.
"""
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

DURACAO = int(os.getenv("DURACAO_SIMULACAO", "3600"))
FIXTURES = Path(__file__).parent / "fixtures"

with open(FIXTURES / "candidatos.json") as f:
    CANDIDATOS = json.load(f)

_inicio = time.time()


def _progresso() -> float:
    """Retorna float 0.0..1.0 representando % da simulação completa."""
    return min((time.time() - _inicio) / DURACAO, 1.0)


def gerar_resultado(uf: str = "sp", cargo: str = "governador") -> dict:
    prog = _progresso()
    pst_pct = round(prog * 100, 2)
    total_votos = int(33_000_000 * prog)
    validos = int(total_votos * 0.92)

    random.seed(int(prog * 100))
    pesos = [0.44, 0.42, 0.10, 0.04]
    votos_cands = []
    restante = validos

    for i, cand in enumerate(CANDIDATOS):
        if i == len(CANDIDATOS) - 1:
            v = restante
        else:
            v = int(validos * pesos[i] * (1 + random.uniform(-0.005, 0.005)))
            restante -= v
        pct = round((v / validos * 100) if validos > 0 else 0, 2)
        situacao = "2º Turno" if i < 2 else "Não Eleito"
        votos_cands.append({
            **cand,
            "vap": str(v),
            "pvap": f"{pct}%",
            "e": situacao,
        })

    return {
        "cdabr": uf,
        "ele": "e000001",
        "carg": f"c000{cargo[:4]}",
        "dt": datetime.now().strftime("%d/%m/%Y"),
        "hor": datetime.now().strftime("%H:%M:%S"),
        "st": "Em andamento" if prog < 1.0 else "Totalizado",
        "pst": f"{pst_pct}%",
        "e": [{
            "cd": uf,
            "nm": f"{uf.upper()} (SIMULADO)",
            "tv": str(total_votos),
            "tvcv": str(validos),
            "pst": f"{pst_pct}%",
            "vnom": votos_cands,
        }],
    }
```

- [ ] **Step 4: Criar simulator/tests/__init__.py** (arquivo vazio)

```bash
touch simulator/tests/__init__.py
```

- [ ] **Step 5: Escrever testes do generator**

Criar `simulator/tests/test_generator.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generator import gerar_resultado

def test_campos_obrigatorios_presentes():
    r = gerar_resultado("sp", "governador")
    assert "cdabr" in r
    assert "pst" in r
    assert "e" in r
    assert "hor" in r
    assert "st" in r

def test_pst_e_percentual_valido():
    r = gerar_resultado("sp", "governador")
    pct = float(r["pst"].replace("%", ""))
    assert 0.0 <= pct <= 100.0

def test_retorna_candidatos():
    r = gerar_resultado("sp", "governador")
    vnom = r["e"][0]["vnom"]
    assert len(vnom) == 4

def test_cada_candidato_tem_campos_obrigatorios():
    r = gerar_resultado("sp", "governador")
    for c in r["e"][0]["vnom"]:
        assert "nm" in c and "vap" in c and "pvap" in c and "e" in c

def test_uf_refletida_no_resultado():
    r = gerar_resultado("rj", "governador")
    assert r["cdabr"] == "rj"
    assert r["e"][0]["cd"] == "rj"
```

- [ ] **Step 6: Executar testes — deve falhar**

```bash
cd ~/Documents/Projetos/megatron/simulator
pip install fastapi uvicorn pytest -q
python3 -m pytest tests/test_generator.py -v
```

Esperado: `ModuleNotFoundError: No module named 'generator'`

- [ ] **Step 7: Implementar simulator/generator.py** (ver código da Task original acima)

- [ ] **Step 8: Executar testes — deve passar**

```bash
python3 -m pytest tests/test_generator.py -v
```

Esperado: 5 testes `PASSED`.

- [ ] **Step 9: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add simulator/fixtures/ simulator/generator.py simulator/tests/
git commit -m "feat(simulator): synthetic data generator with progressive results and tests"
```

---

### Task 4: Servidor FastAPI do Simulador

**Files:**
- Create: `simulator/main.py`
- Create: `simulator/requirements.txt`
- Create: `simulator/Dockerfile`
- Create: `simulator/tests/test_main.py`

- [ ] **Step 1: Criar simulator/requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pytest==8.2.2
httpx==0.27.0
```

- [ ] **Step 2: Escrever testes das rotas do simulador**

Criar `simulator/tests/test_main.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_retorna_modo_sim():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "MEGATRON_SIM"

def test_resultado_variavel_retorna_campos_obrigatorios():
    resp = client.get("/oficial/ele2026/001/dados-simplificados/sp/sp-c0003-e000001-r.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "pst" in data
    assert "e" in data
    assert data["cdabr"] == "sp"

def test_resultado_variavel_extrai_cargo_do_filename():
    resp = client.get("/oficial/ele2026/001/dados-simplificados/rj/rj-c0001-e000001-r.json")
    assert resp.status_code == 200
    assert resp.json()["cdabr"] == "rj"
```

- [ ] **Step 3: Executar testes — deve falhar**

```bash
cd ~/Documents/Projetos/megatron/simulator
pip install -r requirements.txt -q
python3 -m pytest tests/test_main.py -v
```

Esperado: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 4: Implementar simulator/main.py**

```python
"""
Simulador local da CDN do TSE.
Expõe os mesmos endpoints que o TSE real usaria para 2026.
Ativado apenas em modo dev (docker compose --profile dev).
"""
import os
from fastapi import FastAPI
from generator import gerar_resultado
import uvicorn

app = FastAPI(title="Magatron TSE Simulator", version="1.0.0")


@app.get("/oficial/ele2026/{ele}/dados-simplificados/{uf}/{filename}")
async def resultado_variavel(ele: str, uf: str, filename: str):
    """
    Imita: GET /oficial/ele2026/{ele}/dados-simplificados/{uf}/{uf}-c{cargo}-e{ele}-r.json
    Extrai cargo a partir do nome do arquivo: sp-c0003-e000544-r.json → cargo='0003'
    """
    try:
        cargo_code = filename.split("-c")[1].split("-")[0]
    except (IndexError, ValueError):
        cargo_code = "0001"
    return gerar_resultado(uf=uf, cargo=cargo_code)


@app.get("/health")
async def health():
    return {"status": "simulating", "mode": "MEGATRON_SIM"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

- [ ] **Step 5: Criar simulator/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- [ ] **Step 6: Executar todos os testes — deve passar**

```bash
python3 -m pytest tests/ -v
```

Esperado: 8 testes `PASSED` (5 generator + 3 main).

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add simulator/
git commit -m "feat(simulator): FastAPI server mimicking TSE CDN endpoints, with tests"
```

---

## Chunk 3: Collector

### Task 5: URL templates e utilitários do collector

**Files:**
- Create: `collector/tse_urls.py`
- Create: `collector/tests/test_tse_urls.py`
- Create: `collector/requirements.txt`

- [ ] **Step 1: Criar collector/requirements.txt**

```
httpx==0.27.0
redis[asyncio]==5.0.4
apscheduler==3.10.4
# test dependencies
respx==0.21.1
pytest-asyncio==0.23.7
pytest==8.2.2
```

- [ ] **Step 1b: Criar collector/tests/__init__.py** (arquivo vazio)

```bash
mkdir -p collector/tests && touch collector/tests/__init__.py
```

- [ ] **Step 2: Escrever o teste primeiro**

Criar `collector/tests/test_tse_urls.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tse_urls import url_resultado, url_fixos, gerar_tarefas

def test_url_resultado_formato():
    url = url_resultado(base="https://tse.example.com/ele2026", ele="544", uf="sp", cargo="0003")
    assert url == "https://tse.example.com/ele2026/544/dados-simplificados/sp/sp-c0003-e000544-r.json"

def test_url_resultado_ele_com_zero_padding():
    url = url_resultado(base="https://tse.example.com/ele2026", ele="1", uf="rj", cargo="0001")
    assert "-e000001-" in url

def test_url_fixos_formato():
    url = url_fixos(base="https://tse.example.com/ele2026", ele="544", cargo="0003")
    assert url == "https://tse.example.com/ele2026/544/config/ele-c0003-e000544-cf.json"

def test_gerar_tarefas_produto_cartesiano():
    tarefas = gerar_tarefas(ele="544", ufs=["sp", "rj"], cargos=["governador", "presidente"])
    assert len(tarefas) == 4
    ufs_result = {t["uf"] for t in tarefas}
    assert ufs_result == {"sp", "rj"}

def test_gerar_tarefas_campo_stream_key():
    tarefas = gerar_tarefas(ele="544", ufs=["sp"], cargos=["governador"])
    assert tarefas[0]["stream"] == "megatron:sp:governador"
```

- [ ] **Step 3: Executar teste — deve falhar**

```bash
cd ~/Documents/Projetos/megatron/collector
pip install -r requirements.txt -q
python3 -m pytest tests/test_tse_urls.py -v
```

Esperado: `ModuleNotFoundError: No module named 'tse_urls'`

- [ ] **Step 4: Implementar collector/tse_urls.py**

```python
"""
URL templates para os endpoints do TSE e geração de tarefas de coleta.
Todos os parâmetros vêm de variáveis de ambiente — nunca hardcoded.
"""
from itertools import product

CARGO_CODES = {
    "presidente":   "0001",
    "governador":   "0003",
    "senador":      "0005",
    "dep_federal":  "0006",
    "dep_estadual": "0007",
}


def url_resultado(base: str, ele: str, uf: str, cargo: str) -> str:
    """
    URL dos resultados variáveis (polling em tempo real).
    cargo: código de 4 dígitos (ex: '0003') ou nome (ex: 'governador').
    """
    cod = CARGO_CODES.get(cargo, cargo)
    ele_padded = ele.zfill(6)
    return f"{base}/{ele}/dados-simplificados/{uf}/{uf}-c{cod}-e{ele_padded}-r.json"


def url_fixos(base: str, ele: str, cargo: str) -> str:
    """URL dos dados fixos de candidatos (buscar apenas 1x por cargo)."""
    cod = CARGO_CODES.get(cargo, cargo)
    ele_padded = ele.zfill(6)
    return f"{base}/{ele}/config/ele-c{cod}-e{ele_padded}-cf.json"


def gerar_tarefas(ele: str, ufs: list[str], cargos: list[str]) -> list[dict]:
    """
    Produto cartesiano UFs × Cargos → lista de tarefas de coleta.
    Cada tarefa tem: url, uf, cargo, stream (chave Redis).
    """
    # base será injetado em runtime via env; aqui apenas estrutura
    return [
        {
            "uf": uf,
            "cargo": cargo,
            "ele": ele,
            "stream": f"megatron:{uf}:{cargo}",
        }
        for uf, cargo in product(ufs, cargos)
    ]
```

- [ ] **Step 5: Executar teste — deve passar**

```bash
python3 -m pytest tests/test_tse_urls.py -v
```

Esperado: 5 testes `PASSED`.

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add collector/requirements.txt collector/tse_urls.py collector/tests/test_tse_urls.py
git commit -m "feat(collector): TSE URL templates and task generator with tests"
```

---

### Task 6: Fetcher com diff-hash

**Files:**
- Create: `collector/fetcher.py`
- Create: `collector/tests/test_fetcher.py`

- [ ] **Step 1: Escrever teste do fetcher**

Criar `collector/tests/test_fetcher.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import respx
import httpx
from fetcher import fetch_if_changed, _snapshots

HEADERS = {
    "User-Agent": "Magatron/1.0",
    "Referer": "https://resultados.tse.jus.br/",
}

@pytest.fixture(autouse=True)
def clear_snapshots():
    _snapshots.clear()
    yield
    _snapshots.clear()

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_dados_na_primeira_chamada():
    url = "http://tse.example.com/resultado.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={"pst": "10%"}))
    async with httpx.AsyncClient() as client:
        result = await fetch_if_changed(client, url)
    assert result == {"pst": "10%"}

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_none_quando_dados_iguais():
    url = "http://tse.example.com/resultado.json"
    payload = {"pst": "10%"}
    respx.get(url).mock(return_value=httpx.Response(200, json=payload))
    async with httpx.AsyncClient() as client:
        await fetch_if_changed(client, url)       # primeira chamada
        result = await fetch_if_changed(client, url)  # mesmos dados
    assert result is None

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_dados_quando_muda():
    url = "http://tse.example.com/resultado.json"
    async with httpx.AsyncClient() as client:
        respx.get(url).mock(return_value=httpx.Response(200, json={"pst": "10%"}))
        await fetch_if_changed(client, url)
        respx.get(url).mock(return_value=httpx.Response(200, json={"pst": "20%"}))
        result = await fetch_if_changed(client, url)
    assert result == {"pst": "20%"}

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_none_em_erro_http():
    url = "http://tse.example.com/resultado.json"
    respx.get(url).mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        result = await fetch_if_changed(client, url)
    assert result is None

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_none_quando_schema_invalido():
    """Schema validator: payload sem campos obrigatórios deve ser rejeitado."""
    url = "http://tse.example.com/resultado.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={"foo": "bar"}))
    async with httpx.AsyncClient() as client:
        result = await fetch_if_changed(client, url)
    assert result is None
```

- [ ] **Step 2: Instalar dependências de teste e executar — deve falhar**

```bash
cd ~/Documents/Projetos/megatron/collector
pip install respx pytest-asyncio -q
python3 -m pytest tests/test_fetcher.py -v
```

Esperado: `ModuleNotFoundError: No module named 'fetcher'`

- [ ] **Step 3: Implementar collector/fetcher.py**

```python
"""
Fetch com diff-hash: só retorna dados se houve mudança desde a última coleta.
Evita publicações e writes desnecessários no Redis.
Valida schema mínimo do TSE; loga alerta se estrutura mudou (spec: error handling).
"""
import hashlib
import json
import sys

import httpx

HEADERS = {
    "User-Agent": "Magatron/1.0 (Election Monitor)",
    "Accept": "application/json",
    "Referer": "https://resultados.tse.jus.br/",
}

# Campos mínimos obrigatórios no payload TSE
REQUIRED_KEYS = {"pst", "e", "cdabr"}

# Mapa url → hash MD5 do último payload recebido
_snapshots: dict[str, str] = {}


def _hash(data: dict) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


async def fetch_if_changed(client: httpx.AsyncClient, url: str) -> dict | None:
    """
    Faz GET na URL. Retorna o payload se houve mudança desde a última chamada.
    Retorna None se os dados são idênticos, schema inválido, ou se houve erro.
    """
    try:
        r = await client.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Schema validator: alerta se campos obrigatórios estão ausentes
        if not REQUIRED_KEYS.issubset(data.keys()):
            print(
                f"[fetcher] WARNING schema inesperado em {url}: "
                f"keys={list(data.keys())}",
                file=sys.stderr,
            )
            return None
        h = _hash(data)
        if _snapshots.get(url) == h:
            return None
        _snapshots[url] = h
        return data
    except Exception as exc:
        print(f"[fetcher] ERRO ao buscar {url}: {exc}")
        return None
```

- [ ] **Step 4: Executar testes — deve passar**

```bash
python3 -m pytest tests/test_fetcher.py -v
```

Esperado: 4 testes `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add collector/fetcher.py collector/tests/test_fetcher.py
git commit -m "feat(collector): fetch_if_changed with MD5 diff-hash, tests with respx"
```

---

### Task 7: Publisher Redis e Main do Collector

**Files:**
- Create: `collector/publisher.py`
- Create: `collector/tests/test_publisher.py`
- Create: `collector/main.py`
- Create: `collector/Dockerfile`

- [ ] **Step 1: Escrever teste do publisher**

Criar `collector/tests/test_publisher.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, patch
from publisher import publish

@pytest.mark.asyncio
async def test_publish_chama_xadd():
    mock_redis = AsyncMock()
    await publish(mock_redis, "megatron:sp:governador", {"pst": "50%"})
    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == "megatron:sp:governador"
    assert "timestamp" in call_args[0][1]
    assert "data" in call_args[0][1]

@pytest.mark.asyncio
async def test_publish_usa_maxlen():
    mock_redis = AsyncMock()
    await publish(mock_redis, "megatron:sp:governador", {"pst": "50%"})
    call_kwargs = mock_redis.xadd.call_args[1]
    assert call_kwargs.get("maxlen") == 1000

@pytest.mark.asyncio
async def test_publish_serializa_json():
    import json
    mock_redis = AsyncMock()
    data = {"pst": "73.45%", "hor": "22:05:00"}
    await publish(mock_redis, "megatron:sp:governador", data)
    fields = mock_redis.xadd.call_args[0][1]
    parsed = json.loads(fields["data"])
    assert parsed == data
```

- [ ] **Step 2: Executar testes — deve falhar**

```bash
python3 -m pytest tests/test_publisher.py -v
```

Esperado: `ModuleNotFoundError: No module named 'publisher'`

- [ ] **Step 3: Implementar collector/publisher.py**

```python
"""
Publica snapshots de dados eleitorais no Redis Stream.
"""
import json
from datetime import datetime, timezone

import redis.asyncio as aioredis


async def publish(redis_client: aioredis.Redis, stream: str, data: dict) -> None:
    """
    Publica payload no Redis Stream com timestamp UTC.
    maxlen=1000 mantém janela deslizante; dados antigos têm menos valor.
    """
    payload = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "data": json.dumps(data, ensure_ascii=False),
    }
    await redis_client.xadd(stream, payload, maxlen=1000)
    print(f"[publisher] → {stream} | pst={data.get('pst', '?')} | hor={data.get('hor', '?')}")
```

- [ ] **Step 4: Executar testes — deve passar**

```bash
python3 -m pytest tests/test_publisher.py -v
```

Esperado: 3 testes `PASSED`.

- [ ] **Step 5: Implementar collector/main.py**

```python
"""
Entry point do coletor MEGATRON.
APScheduler dispara ciclo_coleta() a cada POLL_INTERVAL_SECONDS.
Em caso de indisponibilidade do Redis, retry exponencial com cap 60s.
Após 10 tentativas falhas, exit(1) para restart pelo Docker.
"""
import asyncio
import os
import sys

import httpx
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fetcher import fetch_if_changed
from publisher import publish
from tse_urls import gerar_tarefas, url_resultado, CARGO_CODES

REDIS_URL       = os.environ["REDIS_URL"]
INTERVALO       = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
TSE_BASE        = os.environ["TSE_BASE_URL"]
ELE_1T          = os.environ["ELE_1T"]
UFS             = [u.strip() for u in os.getenv("UFS", "sp").split(",")]
CARGOS          = [c.strip() for c in os.getenv("CARGOS", "governador").split(",")]

TAREFAS = gerar_tarefas(ele=ELE_1T, ufs=UFS, cargos=CARGOS)


async def ciclo_coleta(redis: aioredis.Redis) -> None:
    async with httpx.AsyncClient() as client:
        for t in TAREFAS:
            u = url_resultado(base=TSE_BASE, ele=t["ele"], uf=t["uf"], cargo=t["cargo"])
            data = await fetch_if_changed(client, u)
            if data:
                await publish(redis, t["stream"], data)
            await asyncio.sleep(1)  # backoff entre requests


async def conectar_redis(max_tentativas: int = 10) -> aioredis.Redis:
    """Conecta ao Redis com retry exponencial. Exit(1) após max_tentativas."""
    delay = 1
    for tentativa in range(1, max_tentativas + 1):
        try:
            r = aioredis.from_url(REDIS_URL)
            await r.ping()
            print(f"[collector] Redis conectado após {tentativa} tentativa(s).")
            return r
        except Exception as e:
            print(f"[collector] Redis indisponível (tentativa {tentativa}/{max_tentativas}): {e}")
            if tentativa == max_tentativas:
                print("[collector] Limite de tentativas atingido. Encerrando.")
                sys.exit(1)
            await asyncio.sleep(min(delay, 60))
            delay *= 2


async def main() -> None:
    redis = await conectar_redis()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        ciclo_coleta,
        "interval",
        seconds=INTERVALO,
        args=[redis],
        max_instances=1,
    )
    scheduler.start()
    print(f"[collector] Iniciado. Intervalo: {INTERVALO}s | Tarefas: {len(TAREFAS)}")
    for t in TAREFAS:
        print(f"  → {t['stream']}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Criar collector/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- [ ] **Step 7: Build do collector**

```bash
cd ~/Documents/Projetos/megatron
docker compose build collector
```

Resultado esperado: build concluído sem erros.

- [ ] **Step 8: Commit**

```bash
git add collector/
git commit -m "feat(collector): publisher, main with exponential backoff, Dockerfile"
```

---

## Chunk 4: API FastAPI

### Task 8: Banco de dados (db.py) e WebSocket Manager

**Files:**
- Create: `api/requirements.txt`
- Create: `api/db.py`
- Create: `api/ws_manager.py`
- Create: `api/tests/conftest.py`
- Create: `api/tests/test_ws_manager.py`

- [ ] **Step 1: Criar api/requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
redis[asyncio]==5.0.4
asyncpg==0.29.0
psycopg2-binary==2.9.9
httpx==0.27.0
pytest==8.2.2
```

- [ ] **Step 2: Escrever teste do WS Manager**

Criar `api/tests/test_ws_manager.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock
from ws_manager import ConnectionManager


@pytest.mark.asyncio
async def test_connect_aceita_websocket_e_adiciona_a_room():
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()
    await mgr.connect(ws, "sp:governador")
    ws.accept.assert_called_once()
    assert ws in mgr.rooms["sp:governador"]


@pytest.mark.asyncio
async def test_disconnect_remove_da_room():
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()
    await mgr.connect(ws, "sp:governador")
    mgr.disconnect(ws, "sp:governador")
    assert ws not in mgr.rooms["sp:governador"]


@pytest.mark.asyncio
async def test_broadcast_envia_para_todos_na_room():
    mgr = ConnectionManager()
    ws1, ws2 = MagicMock(), MagicMock()
    ws1.accept = ws2.accept = AsyncMock()
    ws1.send_text = ws2.send_text = AsyncMock()
    await mgr.connect(ws1, "sp:governador")
    await mgr.connect(ws2, "sp:governador")
    await mgr.broadcast("sp:governador", '{"pst":"50%"}')
    ws1.send_text.assert_called_once_with('{"pst":"50%"}')
    ws2.send_text.assert_called_once_with('{"pst":"50%"}')


@pytest.mark.asyncio
async def test_broadcast_ignora_room_vazia():
    mgr = ConnectionManager()
    # não deve lançar exceção
    await mgr.broadcast("rj:presidente", '{"pst":"0%"}')
```

- [ ] **Step 3: Executar testes — deve falhar**

```bash
cd ~/Documents/Projetos/megatron/api
pip install -r requirements.txt -q
python3 -m pytest tests/test_ws_manager.py -v
```

Esperado: `ModuleNotFoundError: No module named 'ws_manager'`

- [ ] **Step 4: Implementar api/ws_manager.py**

```python
"""
Gerenciador de conexões WebSocket organizadas por "rooms" (uf:cargo).
Thread-safe para uso com asyncio.
"""
from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, room: str) -> None:
        await ws.accept()
        self.rooms[room].append(ws)

    def disconnect(self, ws: WebSocket, room: str) -> None:
        try:
            self.rooms[room].remove(ws)
        except ValueError:
            pass

    async def broadcast(self, room: str, message: str) -> None:
        for ws in list(self.rooms.get(room, [])):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws, room)
```

- [ ] **Step 5: Executar testes — deve passar**

```bash
python3 -m pytest tests/test_ws_manager.py -v
```

Esperado: 4 testes `PASSED`.

- [ ] **Step 6: Criar api/db.py**

```python
"""
Acesso ao TimescaleDB via asyncpg.
get_pool() retorna pool compartilhado criado no startup da API.
"""
import os
from typing import Optional
import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.environ["POSTGRES_URL"],
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def salvar_snapshot(pool: asyncpg.Pool, uf: str, cargo: str, pst_pct: float, payload: dict) -> None:
    """INSERT na hypertable snapshots."""
    import json
    await pool.execute(
        """
        INSERT INTO snapshots (uf, cargo, pst_pct, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        uf, cargo, pst_pct, json.dumps(payload, ensure_ascii=False),
    )


async def buscar_historico(pool: asyncpg.Pool, uf: str, cargo: str, ultimas: int = 20) -> list[dict]:
    """Retorna série temporal de snapshots do mais recente para o mais antigo."""
    rows = await pool.fetch(
        """
        SELECT time, pst_pct, payload
        FROM snapshots
        WHERE uf = $1 AND cargo = $2
        ORDER BY time DESC
        LIMIT $3
        """,
        uf, cargo, ultimas,
    )
    return [
        {"time": str(row["time"]), "pst_pct": float(row["pst_pct"]), "payload": row["payload"]}
        for row in rows
    ]
```

- [ ] **Step 7: Criar api/tests/conftest.py**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.xread = AsyncMock(return_value=[])
    return r
```

- [ ] **Step 8: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add api/
git commit -m "feat(api): ws_manager with rooms, db.py with asyncpg pool and snapshot persistence"
```

---

### Task 9: Consumer, Rotas e Main da API

**Files:**
- Create: `api/consumer.py`
- Create: `api/routes/resultados.py`
- Create: `api/routes/historico.py`
- Create: `api/routes/health.py`
- Create: `api/main.py`
- Create: `api/tests/test_routes.py`
- Create: `api/Dockerfile`

- [ ] **Step 1: Implementar api/consumer.py**

```python
"""
Consome Redis Stream megatron:{uf}:{cargo} e:
1. Faz broadcast via WebSocket para clientes inscritos
2. Persiste snapshot no TimescaleDB
Roda como asyncio task em background.
"""
import json
import os

import redis.asyncio as aioredis

from db import salvar_snapshot
from ws_manager import ConnectionManager

REDIS_URL = os.environ["REDIS_URL"]

# Cache em memória: último snapshot por stream
_last: dict[str, dict] = {}

# Streams monitorados (populado dinamicamente a partir de UFS × CARGOS)
UFS    = [u.strip() for u in os.getenv("UFS", "sp").split(",")]
CARGOS = [c.strip() for c in os.getenv("CARGOS", "governador").split(",")]

STREAMS = {
    f"megatron:{uf}:{cargo}": "$"
    for uf in UFS
    for cargo in CARGOS
}


def get_last_snapshot(stream: str) -> dict | None:
    return _last.get(stream)


async def start_consumer(manager: ConnectionManager, pool) -> None:
    """Inicia loop de consumo do Redis Stream."""
    redis = aioredis.from_url(REDIS_URL)
    streams = dict(STREAMS)
    print(f"[consumer] Aguardando streams: {list(streams.keys())}")

    while True:
        try:
            results = await redis.xread(streams, block=2000, count=10)
        except Exception as e:
            print(f"[consumer] Erro ao ler Redis: {e}")
            continue

        for stream_name_bytes, messages in results:
            stream_key = stream_name_bytes.decode()
            uf, cargo = stream_key.split(":")[1], stream_key.split(":")[2]

            for _, fields in messages:
                raw = fields.get(b"data", b"{}").decode()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                _last[stream_key] = data

                # Broadcast WebSocket
                room = f"{uf}:{cargo}"
                await manager.broadcast(room, raw)

                # Persist TimescaleDB
                try:
                    pst_str = data.get("pst", "0%").replace("%", "")
                    pst_pct = float(pst_str)
                    await salvar_snapshot(pool, uf, cargo, pst_pct, data)
                except Exception as e:
                    print(f"[consumer] Erro ao persistir {stream_key}: {e}")

                streams[stream_key] = "$"  # avança cursor
```

- [ ] **Step 2: Criar api/routes/health.py**

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "service": "megatron-api"}
```

- [ ] **Step 3: Criar api/routes/resultados.py**

```python
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/resultados/{uf}/{cargo}")
async def get_resultado(uf: str, cargo: str):
    from consumer import get_last_snapshot
    snapshot = get_last_snapshot(f"megatron:{uf}:{cargo}")
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Sem dados disponíveis ainda")
    return snapshot
```

- [ ] **Step 4: Criar api/routes/historico.py**

```python
from fastapi import APIRouter, Query
from db import buscar_historico, get_pool

router = APIRouter()

@router.get("/historico/{uf}/{cargo}")
async def get_historico(uf: str, cargo: str, ultimas: int = Query(default=20, ge=1, le=200)):
    pool = await get_pool()
    rows = await buscar_historico(pool, uf, cargo, ultimas)
    return {"uf": uf, "cargo": cargo, "historico": rows}
```

- [ ] **Step 5: Escrever teste de rota**

Criar `api/tests/test_routes.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


def make_app():
    from main import app
    return app


def test_health_retorna_ok():
    with patch("db.get_pool", new_callable=AsyncMock):
        client = TestClient(make_app())
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_resultado_404_quando_sem_dados():
    with patch("consumer.get_last_snapshot", return_value=None):
        with patch("db.get_pool", new_callable=AsyncMock):
            client = TestClient(make_app())
            resp = client.get("/resultados/sp/governador")
    assert resp.status_code == 404


def test_resultado_retorna_snapshot():
    snapshot = {"pst": "50%", "hor": "22:00:00"}
    with patch("consumer.get_last_snapshot", return_value=snapshot):
        with patch("db.get_pool", new_callable=AsyncMock):
            client = TestClient(make_app())
            resp = client.get("/resultados/sp/governador")
    assert resp.status_code == 200
    assert resp.json()["pst"] == "50%"
```

- [ ] **Step 6: Criar api/main.py**

```python
"""
FastAPI application — API pública do MEGATRON.
Expõe REST e WebSocket. Consumer roda como task asyncio em background.
"""
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db import get_pool, close_pool
from ws_manager import ConnectionManager
from consumer import start_consumer
from routes.health import router as health_router
from routes.resultados import router as resultados_router
from routes.historico import router as historico_router

import uvicorn

app = FastAPI(title="Magatron API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(resultados_router)
app.include_router(historico_router)

manager = ConnectionManager()


@app.websocket("/ws/{uf}/{cargo}")
async def websocket_endpoint(websocket: WebSocket, uf: str, cargo: str):
    room = f"{uf}:{cargo}"
    await manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)


@app.on_event("startup")
async def startup():
    pool = await get_pool()
    asyncio.create_task(start_consumer(manager, pool))
    print("[api] Iniciado. Consumer em background.")


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 7: Executar testes da API**

```bash
cd ~/Documents/Projetos/megatron/api
pip install -r requirements.txt pytest httpx -q
python3 -m pytest tests/ -v
```

Esperado: todos os testes `PASSED`.

- [ ] **Step 8: Criar api/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- [ ] **Step 9: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add api/
git commit -m "feat(api): consumer, routes (health/resultados/historico), FastAPI main, Dockerfile"
```

---

## Chunk 5: Frontend

### Task 10: Setup Vite + Tailwind

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`

- [ ] **Step 1: Criar frontend/package.json**

```json
{
  "name": "megatron-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.12.7"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.6",
    "autoprefixer": "^10.4.19",
    "jsdom": "^24.1.0",
    "postcss": "^8.4.39",
    "tailwindcss": "^3.4.6",
    "vite": "^5.3.4",
    "vitest": "^2.0.3"
  }
}
```

- [ ] **Step 2: Criar frontend/vite.config.js**

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    globals: true,
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
  },
});
```

- [ ] **Step 3: Criar frontend/tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0a1a",
        surface: "#12122a",
        primary: "#1565C0",
        success: "#2E7D32",
        muted: "#E8EAF6",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 4: Criar frontend/index.html**

```html
<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MEGATRON — Apuração em Tempo Real</title>
  </head>
  <body class="bg-bg text-muted">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Criar frontend/src/main.jsx**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 6: Criar frontend/src/index.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: Inter, system-ui, sans-serif;
  background-color: #0a0a1a;
  color: #E8EAF6;
  margin: 0;
}
```

- [ ] **Step 7: Instalar dependências**

```bash
cd ~/Documents/Projetos/megatron/frontend
npm install
```

- [ ] **Step 8: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add frontend/
git commit -m "feat(frontend): Vite + React 18 + Tailwind setup"
```

---

### Task 11: Hook useElectionSocket

**Files:**
- Create: `frontend/src/hooks/useElectionSocket.js`
- Create: `frontend/src/test/setup.js`
- Create: `frontend/src/test/useElectionSocket.test.js`

- [ ] **Step 1: Criar setup de testes**

Criar `frontend/src/test/setup.js`:
```javascript
import "@testing-library/jest-dom";
```

- [ ] **Step 2: Escrever teste do hook**

Criar `frontend/src/test/useElectionSocket.test.js`:

```javascript
import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { useElectionSocket } from "../hooks/useElectionSocket";

let mockWs;

class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    mockWs = this;
  }
  close() {}
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useElectionSocket", () => {
  it("inicia desconectado", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    expect(result.current.connected).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it("marca conectado ao onopen", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    act(() => { mockWs.onopen(); });
    expect(result.current.connected).toBe(true);
  });

  it("parseia mensagem JSON recebida", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    act(() => { mockWs.onopen(); });
    act(() => { mockWs.onmessage({ data: '{"pst":"50%"}' }); });
    expect(result.current.data).toEqual({ pst: "50%" });
  });

  it("marca desconectado ao onclose", () => {
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));
    act(() => { mockWs.onopen(); });
    act(() => { mockWs.onclose(); });
    expect(result.current.connected).toBe(false);
  });

  it("usa backoff exponencial na reconexão (2s→4s→cap 30s)", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useElectionSocket("sp", "governador"));

    // 1ª desconexão → delay 2s
    act(() => { mockWs.onopen(); });
    act(() => { mockWs.onclose(); });
    const ws1 = mockWs;
    vi.advanceTimersByTime(1999);
    expect(mockWs).toBe(ws1); // ainda não reconectou
    vi.advanceTimersByTime(1);
    expect(mockWs).not.toBe(ws1); // reconectou após 2s

    // 2ª desconexão → delay 4s
    act(() => { mockWs.onopen(); });
    const ws2 = mockWs;
    act(() => { mockWs.onclose(); });
    vi.advanceTimersByTime(3999);
    expect(mockWs).toBe(ws2);
    vi.advanceTimersByTime(1);
    expect(mockWs).not.toBe(ws2); // reconectou após 4s

    vi.useRealTimers();
  });
});
```

- [ ] **Step 3: Executar testes — deve falhar**

```bash
cd ~/Documents/Projetos/megatron/frontend
npx vitest run src/test/useElectionSocket.test.js
```

Esperado: `Cannot find module '../hooks/useElectionSocket'`

- [ ] **Step 4: Implementar frontend/src/hooks/useElectionSocket.js**

```javascript
import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const BACKOFF_DELAYS = [2000, 4000, 8000, 16000, 30000];

export function useElectionSocket(uf, cargo) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const retryRef = useRef(0);
  const timerRef = useRef(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/${uf}/${cargo}`);

    ws.onopen = () => {
      setConnected(true);
      retryRef.current = 0;
    };

    ws.onmessage = (e) => {
      try { setData(JSON.parse(e.data)); } catch { /* ignora JSON inválido */ }
    };

    ws.onclose = () => {
      setConnected(false);
      const delay = BACKOFF_DELAYS[Math.min(retryRef.current, BACKOFF_DELAYS.length - 1)];
      retryRef.current += 1;
      timerRef.current = setTimeout(connect, delay);
    };

    wsRef.current = ws;
  }, [uf, cargo]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { data, connected };
}
```

- [ ] **Step 5: Executar testes — deve passar**

```bash
npx vitest run src/test/useElectionSocket.test.js
```

Esperado: 4 testes `PASSED`.

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add frontend/src/hooks/ frontend/src/test/
git commit -m "feat(frontend): useElectionSocket hook with exponential backoff reconnect"
```

---

### Task 12: Componentes do Dashboard

**Files:**
- Create: `frontend/src/components/StatusBanner.jsx`
- Create: `frontend/src/components/ProgressBar.jsx`
- Create: `frontend/src/components/CandidatosTable.jsx`
- Create: `frontend/src/components/ResultadoChart.jsx`
- Create: `frontend/src/components/HistoricoChart.jsx`
- Create: `frontend/src/components/Header.jsx`

- [ ] **Step 1: Criar StatusBanner.jsx**

```jsx
export function StatusBanner({ connected, mode }) {
  if (mode === "sim") return (
    <span className="px-3 py-1 rounded-full bg-yellow-900 text-yellow-300 text-sm font-medium">
      🟡 Simulando
    </span>
  );
  return connected ? (
    <span className="px-3 py-1 rounded-full bg-green-900 text-green-300 text-sm font-medium">
      🟢 Ao Vivo
    </span>
  ) : (
    <span className="px-3 py-1 rounded-full bg-red-900 text-red-300 text-sm font-medium">
      🔴 Desconectado
    </span>
  );
}
```

- [ ] **Step 2: Criar ProgressBar.jsx**

```jsx
export function ProgressBar({ pst }) {
  const pct = parseFloat(pst?.replace("%", "") || 0);
  return (
    <div className="mb-6">
      <div className="flex justify-between text-sm text-gray-400 mb-1">
        <span>Seções apuradas</span>
        <span className="text-white font-bold">{pct.toFixed(2)}%</span>
      </div>
      <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-3 bg-primary rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Criar CandidatosTable.jsx**

```jsx
const SITUACAO_COLORS = {
  "Eleito":     "text-green-400",
  "2º Turno":   "text-blue-400",
  "Não Eleito": "text-gray-500",
};

export function CandidatosTable({ candidatos = [] }) {
  if (!candidatos.length) return null;
  const maxVotos = Math.max(...candidatos.map((c) => parseInt(c.vap || 0)));

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-700 mb-6">
      <table className="w-full text-sm">
        <thead className="bg-surface text-gray-400 text-left">
          <tr>
            <th className="px-4 py-3">Nº</th>
            <th className="px-4 py-3">Candidato</th>
            <th className="px-4 py-3">Partido</th>
            <th className="px-4 py-3">Votos</th>
            <th className="px-4 py-3 w-32">%</th>
            <th className="px-4 py-3">Situação</th>
          </tr>
        </thead>
        <tbody>
          {candidatos.map((c, i) => {
            const votos = parseInt(c.vap || 0);
            const pct = parseFloat(c.pvap?.replace("%", "") || 0);
            const barW = maxVotos > 0 ? (votos / maxVotos) * 100 : 0;
            return (
              <tr key={c.sqcand} className={`border-t border-gray-800 ${i === 0 ? "bg-blue-950" : ""}`}>
                <td className="px-4 py-3 font-mono text-gray-400">{c.n}</td>
                <td className="px-4 py-3 font-semibold">{c.nm}</td>
                <td className="px-4 py-3 text-gray-400">{c.sg}</td>
                <td className="px-4 py-3 font-mono">{votos.toLocaleString("pt-BR")}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-800 rounded-full">
                      <div className="h-2 bg-primary rounded-full" style={{ width: `${barW}%` }} />
                    </div>
                    <span className="text-xs w-10 text-right">{pct.toFixed(1)}%</span>
                  </div>
                </td>
                <td className={`px-4 py-3 ${SITUACAO_COLORS[c.e] || "text-gray-400"}`}>{c.e}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Criar ResultadoChart.jsx**

```jsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const CORES = ["#1565C0", "#B71C1C", "#2E7D32", "#6A1B9A", "#E65100"];

export function ResultadoChart({ candidatos = [] }) {
  if (!candidatos.length) return null;
  const dados = candidatos.map((c) => ({
    nome: c.nm.split(" ")[0],
    votos: parseInt(c.vap || 0),
  }));

  return (
    <div className="bg-surface rounded-xl p-4 mb-6">
      <h3 className="text-sm text-gray-400 mb-3">Distribuição de votos</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={dados} layout="vertical" margin={{ left: 10 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="nome" width={90} tick={{ fill: "#E8EAF6", fontSize: 12 }} />
          <Tooltip
            formatter={(v) => v.toLocaleString("pt-BR")}
            contentStyle={{ background: "#12122a", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#E8EAF6" }}
          />
          <Bar dataKey="votos" radius={[0, 6, 6, 0]}>
            {dados.map((_, i) => <Cell key={i} fill={CORES[i % CORES.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 5: Criar HistoricoChart.jsx**

```jsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function HistoricoChart({ historico = [] }) {
  if (!historico.length) return null;
  const dados = [...historico].reverse().map((h) => ({
    hora: new Date(h.time).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    pct: parseFloat(h.pst_pct),
  }));

  return (
    <div className="bg-surface rounded-xl p-4 mb-6">
      <h3 className="text-sm text-gray-400 mb-3">Evolução da apuração</h3>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={dados}>
          <XAxis dataKey="hora" tick={{ fill: "#E8EAF6", fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#E8EAF6", fontSize: 11 }} unit="%" />
          <Tooltip
            formatter={(v) => `${v.toFixed(2)}%`}
            contentStyle={{ background: "#12122a", border: "1px solid #334155", borderRadius: 8 }}
          />
          <Line type="monotone" dataKey="pct" stroke="#1565C0" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 6: Criar Header.jsx**

```jsx
import { StatusBanner } from "./StatusBanner";

const UFS_OPCOES = ["sp", "rj", "mg", "rs", "ba", "pr", "pe", "ce", "pa", "sc"];
const CARGOS_OPCOES = ["governador", "presidente", "senador", "dep_federal"];

export function Header({ uf, cargo, connected, onUfChange, onCargoChange }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 mb-8 pb-4 border-b border-gray-800">
      <h1 className="text-xl font-bold tracking-wide">
        🗳️ <span className="text-primary">MEGATRON</span>
      </h1>
      <div className="flex items-center gap-3">
        <select
          value={uf}
          onChange={(e) => onUfChange(e.target.value)}
          className="bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm uppercase"
        >
          {UFS_OPCOES.map((u) => <option key={u} value={u}>{u.toUpperCase()}</option>)}
        </select>
        <select
          value={cargo}
          onChange={(e) => onCargoChange(e.target.value)}
          className="bg-surface border border-gray-700 rounded-lg px-3 py-2 text-sm capitalize"
        >
          {CARGOS_OPCOES.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
        </select>
        <StatusBanner connected={connected} />
      </div>
    </header>
  );
}
```

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add frontend/src/components/
git commit -m "feat(frontend): dashboard components — table, charts, progress bar, header"
```

---

### Task 13: App.jsx, Dockerfile e build de produção

**Files:**
- Create: `frontend/src/App.jsx`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: Criar frontend/src/App.jsx**

```jsx
import { useState, useEffect } from "react";
import { useElectionSocket } from "./hooks/useElectionSocket";
import { Header } from "./components/Header";
import { ProgressBar } from "./components/ProgressBar";
import { CandidatosTable } from "./components/CandidatosTable";
import { ResultadoChart } from "./components/ResultadoChart";
import { HistoricoChart } from "./components/HistoricoChart";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [uf, setUf] = useState("sp");
  const [cargo, setCargo] = useState("governador");
  const [historico, setHistorico] = useState([]);

  const { data, connected } = useElectionSocket(uf, cargo);
  const estado = data?.e?.[0];

  // Busca histórico ao trocar UF/cargo ou ao receber novo dado
  useEffect(() => {
    fetch(`${API_URL}/historico/${uf}/${cargo}?ultimas=30`)
      .then((r) => r.json())
      .then((d) => setHistorico(d.historico || []))
      .catch(() => {});
  }, [uf, cargo, data?.hor]);

  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Header
          uf={uf}
          cargo={cargo}
          connected={connected}
          onUfChange={setUf}
          onCargoChange={setCargo}
        />

        {estado ? (
          <>
            <div className="bg-surface rounded-xl p-4 mb-6">
              <p className="text-gray-400 text-sm mb-1">{estado.nm}</p>
              <p className="text-xs text-gray-500">
                {data.st} · Atualizado às {data.hor}
              </p>
            </div>

            <ProgressBar pst={estado.pst} />
            <ResultadoChart candidatos={estado.vnom} />
            <CandidatosTable candidatos={estado.vnom} />
            <HistoricoChart historico={historico} />
          </>
        ) : (
          <div className="text-center text-gray-500 mt-20">
            <p className="text-4xl mb-4">🗳️</p>
            <p>Aguardando dados de apuração...</p>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Criar frontend/nginx.conf**

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /health {
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }
}
```

- [ ] **Step 3: Criar frontend/Dockerfile (multi-stage)**

```dockerfile
# Stage 1: build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ARG VITE_WS_URL=ws://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
RUN npm run build

# Stage 2: serve via nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

- [ ] **Step 4: Build de teste do frontend**

```bash
cd ~/Documents/Projetos/megatron/frontend
npm run build
```

Esperado: `dist/` criado sem erros.

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/Projetos/megatron
git add frontend/src/App.jsx frontend/Dockerfile frontend/nginx.conf
git commit -m "feat(frontend): App.jsx dashboard completo, Dockerfile multi-stage nginx"
```

---

## Chunk 6: Integração e Smoke Test

### Task 14: Teste de integração completo (modo dev)

**Files:**
- Create: `scripts/test_endpoints.py`

- [ ] **Step 1: Criar scripts/test_endpoints.py**

```python
#!/usr/bin/env python3
"""
Smoke test: verifica se todos os serviços da stack estão respondendo.
Executar com a stack rodando: docker compose --profile dev up -d
"""
import sys
import httpx

BASE_API = "http://localhost:8000"
BASE_SIM = "http://localhost:8001"

CHECKS = [
    (f"{BASE_API}/health",                     "API health"),
    (f"{BASE_SIM}/health",                     "Simulator health"),
    (f"{BASE_API}/resultados/sp/governador",   "API resultados (pode ser 404 se sem dados)"),
    (f"{BASE_API}/historico/sp/governador",    "API historico"),
]

def run():
    ok = True
    for url, label in CHECKS:
        try:
            r = httpx.get(url, timeout=5)
            status = "✅" if r.status_code < 500 else "❌"
            print(f"  {status} {label}: HTTP {r.status_code}")
            if r.status_code >= 500:
                ok = False
        except Exception as e:
            print(f"  ❌ {label}: {e}")
            ok = False
    return ok

if __name__ == "__main__":
    print("🔍 Magatron Smoke Test\n")
    if run():
        print("\n✅ Todos os checks passaram.")
        sys.exit(0)
    else:
        print("\n❌ Alguns checks falharam.")
        sys.exit(1)
```

- [ ] **Step 2: Subir a stack completa em modo dev**

```bash
cd ~/Documents/Projetos/megatron

# Copiar .env se ainda não existe
cp .env.example .env
# Editar .env: ELE_1T=001  (placeholder para o simulador)
# TSE_BASE_URL=http://simulator:8001/oficial/ele2026

TSE_BASE_URL=http://simulator:8001/oficial/ele2026 \
ELE_1T=001 \
docker compose --profile dev up --build -d

# Aguardar healthchecks passarem (--wait bloqueia até todos os serviços healthy)
docker compose --profile dev up --wait
```

- [ ] **Step 3: Inicializar o banco**

```bash
docker compose exec api python -c "
import asyncio, os
os.environ['POSTGRES_URL'] = 'postgresql://megatron:change-me-in-production@timescaledb/megatron'
import sys; sys.path.insert(0, '/app')
from db import get_pool
import asyncpg

async def seed():
    conn = await asyncpg.connect(os.environ['POSTGRES_URL'])
    await conn.execute('CREATE EXTENSION IF NOT EXISTS timescaledb;')
    await conn.execute('''CREATE TABLE IF NOT EXISTS snapshots (
        time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        uf TEXT NOT NULL, cargo TEXT NOT NULL,
        pst_pct NUMERIC(5,2), payload JSONB
    );''')
    try:
        await conn.execute(\"SELECT create_hypertable('snapshots', 'time', if_not_exists => TRUE);\")
    except Exception: pass
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_s ON snapshots (uf, cargo, time DESC);')
    await conn.close()
    print('Schema OK')
asyncio.run(seed())
"
```

Ou rodar diretamente:
```bash
POSTGRES_URL="postgresql://megatron:change-me-in-production@localhost:5432/megatron" \
  python3 scripts/seed_db.py
```

- [ ] **Step 4: Executar smoke test**

```bash
python3 scripts/test_endpoints.py
```

Resultado esperado:
```
🔍 Magatron Smoke Test

  ✅ API health: HTTP 200
  ✅ Simulator health: HTTP 200
  ✅ API resultados (pode ser 404 se sem dados): HTTP 200 ou 404
  ✅ API historico: HTTP 200

✅ Todos os checks passaram.
```

- [ ] **Step 5: Verificar WebSocket manualmente**

```bash
# Instalar wscat se necessário: npm install -g wscat
wscat -c ws://localhost:8000/ws/sp/governador
# Aguardar 60s e verificar que recebe JSON do simulador
```

- [ ] **Step 6: Verificar frontend**

```bash
open http://localhost:3000
```

Verificar: header com seletor, progress bar aparece após ~60s (primeiro ciclo do collector).

- [ ] **Step 7: Commit final**

```bash
cd ~/Documents/Projetos/megatron
git add scripts/test_endpoints.py
git commit -m "feat(scripts): smoke test for all services"
```

---

## Referência Rápida

### Subir em modo dev (simulador)
```bash
TSE_BASE_URL=http://simulator:8001/oficial/ele2026 ELE_1T=001 \
docker compose --profile dev up --build
```

### Subir em modo produção (TSE real)
```bash
# .env: ELE_1T=<codigo_publicado_pelo_TSE>
docker compose up --build
docker compose logs -f collector
```

### Acelerar simulação (testes)
```bash
DURACAO_SIMULACAO=120 TSE_BASE_URL=http://simulator:8001/oficial/ele2026 ELE_1T=001 \
docker compose --profile dev up --build
```

### Rodar todos os testes Python
```bash
cd collector && python3 -m pytest tests/ -v
cd ../api && python3 -m pytest tests/ -v
```

### Rodar testes frontend
```bash
cd frontend && npm test
```
