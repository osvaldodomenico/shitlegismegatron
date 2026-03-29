# MAGATRON — Design Spec
**Data:** 2026-03-29
**Status:** Aprovado
**Ciclo eleitoral alvo:** Eleições 2026 (Brasil)
**Localização do projeto:** `~/Documents/Projetos/magatron`

---

## Objetivo

Construir o **MAGATRON**: sistema de ingestão, processamento e exibição em tempo real de dados de apuração eleitoral. Consome a API pública JSON do TSE, com simulador local para desenvolvimento. Dashboard público com visual noturno de apuração.

---

## Decisões Arquiteturais

| Decisão | Escolha | Motivo |
|---|---|---|
| Frontend build | Vite + React 18 | CRA obsoleto; Vite 10-20x mais rápido |
| Estilo frontend | Tailwind CSS + recharts | Utilitário rápido + gráficos interativos |
| Persistência Redis | Consumer da API persiste no Timescale | Elimina serviço processador extra |
| Modo dev | `--profile dev` no Docker Compose | Isola simulador, 1 único compose file |
| Parametrização | `TSE_BASE_URL` via `.env` | Troca simulador↔TSE real sem código |

---

## Arquitetura

```
[TSE CDN / Simulator]
        │ HTTP
        ▼
   [Collector]          APScheduler · httpx · diff hash
        │ xadd
        ▼
     [Redis]            Streams: magatron:{uf}:{cargo}
        │ xread
        ▼
   [API FastAPI]        consumer.py (asyncio task background)
    ├─▶ WebSocket /ws/{uf}/{cargo}   → broadcast para clientes
    ├─▶ REST GET /resultados/{uf}/{cargo}
    ├─▶ REST GET /historico/{uf}/{cargo}
    └─▶ INSERT TimescaleDB
        │
   [TimescaleDB]        hypertable: snapshots(time, uf, cargo, pst_pct, payload)

   [Frontend Vite]      React 18 · Tailwind · recharts · WebSocket nativo
```

---

## Serviços Docker

| Serviço | Imagem | Porta | Profile |
|---|---|---|---|
| `redis` | redis:7-alpine | 6379 | sempre |
| `timescaledb` | timescale/timescaledb:latest-pg15 | 5432 | sempre |
| `collector` | python:3.11-slim | — | sempre |
| `api` | python:3.11-slim | 8000 | sempre |
| `simulator` | python:3.11-slim | 8001 | `dev` |
| `frontend` | node:20-alpine → nginx | 3000 | sempre |

---

## Módulos

### `collector/`
- **Responsabilidade:** Único ponto de fetch de dados externos
- `APScheduler` dispara `ciclo_coleta()` a cada `POLL_INTERVAL_SECONDS` (padrão: 60s)
- `fetch_if_changed()` — hash MD5 do payload; só publica se houve mudança
- Publica em Redis Stream `magatron:{uf}:{cargo}` via `xadd` (maxlen=1000)
- Backoff 1s entre requests; `User-Agent` e `Referer` corretos para evitar rate-limit
- `TAREFAS` dinâmicas: geradas a partir de `UFS` e `CARGOS` no `.env`

### `simulator/`
- **Responsabilidade:** Imitar CDN do TSE em modo dev (perfil Docker `dev`)
- Serve os endpoints com estrutura idêntica ao TSE real
- Progresso 0%→100% em `DURACAO_SIMULACAO` segundos (default 3600)
- Fixtures com candidatos fictícios mas estrutura JSON realista
- `GET /health` retorna `{"mode": "MAGATRON_SIM"}`

### `api/`
- **Responsabilidade:** Gateway público + persistência
- `consumer.py`: task asyncio que roda em background via `startup` event
  - `xread` bloqueante no Redis, avança cursor `$` após cada leitura
  - Broadcast via `ConnectionManager` para todos os WS inscritos na room `{uf}:{cargo}`
  - INSERT na hypertable Timescale (time=NOW, uf, cargo, pst_pct, payload jsonb)
- REST: `GET /resultados/{uf}/{cargo}` — último snapshot do Redis cache em memória
- REST: `GET /historico/{uf}/{cargo}?ultimas=20` — série temporal do Timescale
- WebSocket: `/ws/{uf}/{cargo}` — cliente recebe atualizações em tempo real
- CORS aberto (público)

### `frontend/`
- **Responsabilidade:** Dashboard público de apuração (dark, responsivo)
- Seletor de UF e cargo no header
- Progress bar de seções apuradas (%)
- Tabela de candidatos com barras inline de votos
- Gráfico horizontal de barras (recharts BarChart) por candidato
- Gráfico de linha temporal (recharts LineChart) — evolução do % apurado via REST `/historico`
- Status banner: 🟢 Ao Vivo / 🔴 Desconectado / 🟡 Simulando
- Reconexão automática ao WebSocket após 5s de queda

### `scripts/`
- `seed_db.py`: cria extensão TimescaleDB + hypertable + índices na primeira execução
- `test_endpoints.py`: verifica se endpoints do TSE 2026 respondem (smoke test)

---

## Schema de Dados

### TimescaleDB

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS snapshots (
    time        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    uf          TEXT            NOT NULL,
    cargo       TEXT            NOT NULL,
    pst_pct     NUMERIC(5,2),
    payload     JSONB
);

SELECT create_hypertable('snapshots', 'time', if_not_exists => TRUE);

CREATE INDEX ON snapshots (uf, cargo, time DESC);
```

### Redis Streams

**Key:** `magatron:{uf}:{cargo}`
**Fields por mensagem:**
```
timestamp  →  ISO 8601 UTC
data       →  JSON string do payload TSE
```

---

## Variáveis de Ambiente (`.env.example`)

```env
# TSE / Simulador
TSE_BASE_URL=https://resultados.tse.jus.br/oficial/ele2026
POLL_INTERVAL_SECONDS=60

# Eleição alvo (2026: códigos a definir após publicação TSE)
ELE_1T=TBD
ELE_2T=TBD

# Monitoramento
UFS=sp,rj,mg,rs,ba,pr,pe,ce,pa,sc,br
CARGOS=presidente,governador,senador,dep_federal

# Infra
REDIS_URL=redis://redis:6379
POSTGRES_URL=postgresql://magatron:magatron123@timescaledb/magatron

# Simulador (dev)
DURACAO_SIMULACAO=3600
```

---

## Execução

### Modo Dev (simulador)
```bash
TSE_BASE_URL=http://simulator:8001/oficial/ele2026 \
docker compose --profile dev up --build
```

### Modo Produção (TSE real — dia da eleição)
```bash
# Editar .env: ELE_1T=<codigo_2026>
docker compose up --build
docker compose logs -f collector
```

### Acelerar simulação (para testes)
```bash
DURACAO_SIMULACAO=600 docker compose --profile dev up
```

---

## Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| Timeout fetch TSE | Log + skip ciclo (retry no próximo intervalo) |
| TSE retorna mesmos dados | Hash MD5 igual → não publica no Redis |
| Redis indisponível | Collector tenta reconectar com backoff exponencial |
| TimescaleDB indisponível | API loga erro, continua servindo WS sem persistência |
| WS cliente desconecta | `ConnectionManager.disconnect()` remove da room silenciosamente |
| Mudança de estrutura JSON | Schema validator no fetcher + log de alerta |

---

## Frontend — Visual

| Elemento | Valor |
|---|---|
| Background | `#0a0a1a` |
| Card surface | `#12122a` |
| Accent primário | `#1565C0` (azul TSE) |
| Accent sucesso | `#2E7D32` |
| Texto principal | `#E8EAF6` |
| Fonte | Inter / system-ui |
| Dark mode | Padrão (sempre ativo) |

---

## Roadmap de Desenvolvimento

```
Fase 1 — Simulação (atual)
  ✅ Estrutura base + Docker Compose
  ✅ Simulador (0% → 100%)
  ✅ Collector + Redis Stream
  ✅ API WebSocket + REST + seed Timescale
  ✅ Frontend Vite: dashboard completo

Fase 2 — Produção (dia da eleição 2026)
  🔄 Troca TSE_BASE_URL → produção real
  🔄 Atualizar ELE_1T com código publicado pelo TSE
  🔄 Alertas de variação > 2% num ciclo

Fase 3 — Pós-eleição
  📊 Exportação CSV/JSON do histórico
  📊 Comparativo de turnos
```

---

## Notas Técnicas

1. O campo `hor` no JSON do TSE é o indicador confiável de timestamp dos dados — sempre logar.
2. Os códigos de eleição (`ele`) para 2026 serão publicados pelo TSE próximo à eleição. Toda a stack usa `ELE_1T`/`ELE_2T` do `.env`.
3. `User-Agent: Magatron/1.0` + `Referer: https://resultados.tse.jus.br/` são necessários para evitar bloqueios da CDN.
4. O diff hash no `fetcher.py` é crítico — evita escritas e broadcasts com dados idênticos.
5. `maxlen=1000` no Redis Stream limita memória sem perder relevância (apuração é progressiva, dados antigos têm menos valor).

---

*Spec gerado em sessão brainstorming · MAGATRON · 2026-03-29*
