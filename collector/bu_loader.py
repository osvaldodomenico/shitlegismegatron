"""
Carregador dos BOLETINS DE URNA no Postgres, em lotes, validando.

Le os bu.dat que o collector_urnas ja baixou (indice em `urna_secao`),
decodifica (bu.py) e grava:
  urna_bu     -> uma linha por secao: local, emissao, aptos, comparecimento,
                 consistencia interna (soma dos votos == comparecimento x
                 votos por eleitor, para TODOS os cargos), hash do arquivo.
  urna_votos  -> uma linha por (secao, eleicao, cargo, tipo de voto, partido,
                 numero): os votos. E daqui que saem escola e bairro, via
                 locais_votacao.
  urna_validacao -> por cidade e cargo: soma dos votos nominais das secoes
                 carregadas x total nominal do boletim da cidade (TSE,
                 votos_municipio). Quando todas as secoes da cidade estao
                 carregadas e o boletim da cidade esta em 100%, tem que bater.

Lotes de BU_LOTE secoes por transacao; o que falhar na decodificacao fica
marcado em urna_secao.bu_erro e nao trava o resto. Reprocessa uma secao se
o hash do arquivo mudou.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis

from bu import ler_boletim

POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")
UFS = [u.strip().lower() for u in os.environ.get("URNA_UFS", "sp").split(",") if u.strip()]
LOTE = int(os.environ.get("BU_LOTE", "500"))
INTERVALO = int(os.environ.get("BU_INTERVAL_SECONDS", "600"))
HEARTBEAT = "megatron:heartbeat:bu"

DDL = """
ALTER TABLE urna_secao ADD COLUMN IF NOT EXISTS bu_hash TEXT;      -- hash do bu ja carregado
ALTER TABLE urna_secao ADD COLUMN IF NOT EXISTS bu_erro TEXT;

CREATE TABLE IF NOT EXISTS urna_bu (
    uf            TEXT NOT NULL,
    cod_mun       TEXT NOT NULL,
    zona          INT  NOT NULL,
    secao         INT  NOT NULL,
    local         INT,
    emissao       TEXT,
    aptos         JSONB,                 -- idEleicao -> eleitores aptos
    comparecimento INT,
    lib_codigo    INT,
    consistente   BOOLEAN,
    detalhe       JSONB,                 -- por cargo: soma, comparecimento, votos_por_eleitor
    hash          TEXT,
    carregado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uf, cod_mun, zona, secao)
);
CREATE TABLE IF NOT EXISTS urna_votos (
    uf        TEXT NOT NULL,
    cod_mun   TEXT NOT NULL,
    zona      INT  NOT NULL,
    secao     INT  NOT NULL,
    eleicao   INT  NOT NULL,
    cargo     TEXT NOT NULL,
    tipo      TEXT NOT NULL,            -- nominal | branco | nulo | legenda
    partido   INT  NOT NULL DEFAULT 0,
    codigo    INT  NOT NULL DEFAULT 0,  -- numero de urna (nominal) / partido (legenda) / 0
    votos     INT  NOT NULL,
    PRIMARY KEY (uf, cod_mun, zona, secao, eleicao, cargo, tipo, partido, codigo)
);
CREATE INDEX IF NOT EXISTS urna_votos_cand_idx ON urna_votos (uf, cargo, codigo);
CREATE INDEX IF NOT EXISTS urna_votos_mun_idx ON urna_votos (uf, cod_mun, cargo);

CREATE TABLE IF NOT EXISTS urna_validacao (
    uf            TEXT NOT NULL,
    cod_mun       TEXT NOT NULL,
    cargo         TEXT NOT NULL,
    secoes_cadastro INT,
    secoes_bu     INT,
    pst_cidade    NUMERIC(5,2),
    nominais_bu   BIGINT,
    nominais_tse  BIGINT,
    diferenca     BIGINT,
    status        TEXT,                 -- ok | incompleto | DIVERGE
    validado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uf, cod_mun, cargo)
);

-- Votos por candidato por ESCOLA (local de votacao) e por BAIRRO.
DROP VIEW IF EXISTS votos_por_local;
CREATE VIEW votos_por_local AS
SELECT v.uf, v.cod_mun, l.nm_municipio AS municipio, v.zona, l.nr_local_votacao AS local,
       l.nm_local_votacao AS escola, l.ds_endereco AS endereco, l.nm_bairro AS bairro,
       v.cargo, v.tipo, v.partido, v.codigo AS numero, SUM(v.votos) AS votos,
       COUNT(DISTINCT v.secao) AS secoes
FROM urna_votos v
JOIN locais_votacao l
  ON upper(l.sg_uf) = upper(v.uf) AND l.cd_municipio = v.cod_mun AND l.nr_zona = v.zona AND l.nr_secao = v.secao
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12;

DROP VIEW IF EXISTS votos_por_bairro;
CREATE VIEW votos_por_bairro AS
SELECT v.uf, v.cod_mun, l.nm_municipio AS municipio, l.nm_bairro AS bairro,
       v.cargo, v.tipo, v.partido, v.codigo AS numero, SUM(v.votos) AS votos,
       COUNT(DISTINCT (v.zona, v.secao)) AS secoes
FROM urna_votos v
JOIN locais_votacao l
  ON upper(l.sg_uf) = upper(v.uf) AND l.cd_municipio = v.cod_mun AND l.nr_zona = v.zona AND l.nr_secao = v.secao
GROUP BY 1,2,3,4,5,6,7,8;
"""


async def preparar(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con:
        await con.execute(DDL)


async def pendentes(pool: asyncpg.Pool, uf: str, limite: int) -> list[asyncpg.Record]:
    """Secoes com bu no disco cujo hash ainda nao foi carregado (ou mudou)."""
    async with pool.acquire() as con:
        return await con.fetch(
            """
            SELECT cod_mun, zona, secao, hash, arquivos->'bu'->>'caminho' AS caminho
            FROM urna_secao
            WHERE uf = $1 AND arquivos ? 'bu' AND hash IS NOT NULL
              AND (bu_hash IS NULL OR bu_hash <> hash)
            ORDER BY cod_mun, zona, secao
            LIMIT $2
            """, uf, limite)


async def carregar_lote(pool: asyncpg.Pool, uf: str, linhas: list[asyncpg.Record]) -> dict:
    cont = {"ok": 0, "inconsistente": 0, "erro": 0, "votos": 0}
    for r in linhas:
        caminho = r["caminho"]
        try:
            raw = Path(caminho).read_bytes()
            b = ler_boletim(raw)
            if (b.municipio, b.zona, b.secao) != (int(r["cod_mun"]), int(r["zona"]), int(r["secao"])):
                raise ValueError(f"BU identifica {b.municipio}/{b.zona}/{b.secao}, esperado {r['cod_mun']}/{r['zona']}/{r['secao']}")
            detalhe = {x.cargo: {"soma": x.soma(), "comparecimento": x.comparecimento,
                                 "votos_por_eleitor": x.votos_por_eleitor} for x in b.resultados}
            comparecimento = max((x.comparecimento for x in b.resultados), default=0)
            votos = [(uf, r["cod_mun"], int(r["zona"]), int(r["secao"]), x.eleicao, x.cargo, v.tipo,
                      v.partido or 0, v.codigo or 0, v.votos)
                     for x in b.resultados for v in x.votaveis]
            async with pool.acquire() as con:
                async with con.transaction():
                    await con.execute("DELETE FROM urna_votos WHERE uf=$1 AND cod_mun=$2 AND zona=$3 AND secao=$4",
                                      uf, r["cod_mun"], int(r["zona"]), int(r["secao"]))
                    await con.executemany(
                        """INSERT INTO urna_votos (uf, cod_mun, zona, secao, eleicao, cargo, tipo, partido, codigo, votos)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                           ON CONFLICT (uf, cod_mun, zona, secao, eleicao, cargo, tipo, partido, codigo)
                           DO UPDATE SET votos = urna_votos.votos + EXCLUDED.votos""", votos)
                    await con.execute(
                        """INSERT INTO urna_bu (uf, cod_mun, zona, secao, local, emissao, aptos, comparecimento,
                                                lib_codigo, consistente, detalhe, hash, carregado_em)
                           VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11::jsonb,$12,NOW())
                           ON CONFLICT (uf, cod_mun, zona, secao) DO UPDATE SET
                             local=EXCLUDED.local, emissao=EXCLUDED.emissao, aptos=EXCLUDED.aptos,
                             comparecimento=EXCLUDED.comparecimento, lib_codigo=EXCLUDED.lib_codigo,
                             consistente=EXCLUDED.consistente, detalhe=EXCLUDED.detalhe, hash=EXCLUDED.hash,
                             carregado_em=NOW()""",
                        uf, r["cod_mun"], int(r["zona"]), int(r["secao"]), b.local, b.emissao,
                        json.dumps({str(k): v for k, v in b.aptos.items()}), comparecimento, b.eleitores_lib_codigo,
                        b.consistente(), json.dumps(detalhe), r["hash"])
                    await con.execute("UPDATE urna_secao SET bu_hash=$5, bu_erro=NULL WHERE uf=$1 AND cod_mun=$2 AND zona=$3 AND secao=$4",
                                      uf, r["cod_mun"], int(r["zona"]), int(r["secao"]), r["hash"])
            cont["ok" if b.consistente() else "inconsistente"] += 1
            cont["votos"] += len(votos)
        except Exception as e:  # noqa: BLE001
            cont["erro"] += 1
            async with pool.acquire() as con:
                await con.execute("UPDATE urna_secao SET bu_erro=$5 WHERE uf=$1 AND cod_mun=$2 AND zona=$3 AND secao=$4",
                                  uf, r["cod_mun"], int(r["zona"]), int(r["secao"]), str(e)[:300])
            print(f"[bu] erro {uf} {r['cod_mun']}/{r['zona']}/{r['secao']}: {e}", file=sys.stderr)
    return cont


async def validar(pool: asyncpg.Pool, uf: str) -> dict:
    """
    Cidade x cargo: nominais somados das secoes carregadas x nominais do
    boletim da cidade (TSE). 'ok' quando todas as secoes do cadastro estao
    carregadas, a cidade esta em 100% e a diferenca e zero; 'incompleto'
    enquanto faltam secoes ou o boletim da cidade nao fechou; 'DIVERGE' se
    tudo esta completo e ainda assim nao bate.
    """
    async with pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO urna_validacao (uf, cod_mun, cargo, secoes_cadastro, secoes_bu, pst_cidade,
                                        nominais_bu, nominais_tse, diferenca, status, validado_em)
            SELECT c.uf, c.cod_mun, c.cargo, c.secoes_cadastro, b.secoes_bu, m.pst,
                   b.nominais_bu, m.nominais, b.nominais_bu - m.nominais,
                   CASE WHEN b.secoes_bu >= c.secoes_cadastro AND m.pst >= 100 AND b.nominais_bu = m.nominais THEN 'ok'
                        WHEN b.secoes_bu >= c.secoes_cadastro AND m.pst >= 100 THEN 'DIVERGE'
                        ELSE 'incompleto' END,
                   NOW()
            FROM (SELECT $1::text AS uf, l.cd_municipio AS cod_mun, x.cargo, COUNT(*) AS secoes_cadastro
                  FROM locais_votacao l CROSS JOIN (VALUES ('presidente'),('governador'),('senador'),('dep_federal'),('dep_estadual')) AS x(cargo)
                  WHERE upper(l.sg_uf) = upper($1) GROUP BY 1,2,3) c
            JOIN (SELECT uf, cod_mun, cargo, COUNT(DISTINCT (zona, secao)) AS secoes_bu,
                         SUM(votos) FILTER (WHERE tipo = 'nominal') AS nominais_bu
                  FROM urna_votos WHERE uf = $1 GROUP BY 1,2,3) b USING (uf, cod_mun, cargo)
            LEFT JOIN votos_municipio m ON m.uf = $1 AND m.nivel = 'municipio' AND m.cod_tse = c.cod_mun AND m.cargo = c.cargo
            ON CONFLICT (uf, cod_mun, cargo) DO UPDATE SET
              secoes_cadastro=EXCLUDED.secoes_cadastro, secoes_bu=EXCLUDED.secoes_bu, pst_cidade=EXCLUDED.pst_cidade,
              nominais_bu=EXCLUDED.nominais_bu, nominais_tse=EXCLUDED.nominais_tse, diferenca=EXCLUDED.diferenca,
              status=EXCLUDED.status, validado_em=NOW()
            """, uf)
        rows = await con.fetch("SELECT status, COUNT(*) n FROM urna_validacao WHERE uf=$1 GROUP BY 1", uf)
    return {r["status"]: r["n"] for r in rows}


async def main() -> None:
    if not POSTGRES_URL or not REDIS_URL:
        print("[bu] faltam POSTGRES_URL/REDIS_URL", file=sys.stderr)
        sys.exit(1)
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    redis = aioredis.from_url(REDIS_URL)
    await preparar(pool)
    while True:
        inicio = time.monotonic()
        total = {"ok": 0, "inconsistente": 0, "erro": 0, "votos": 0}
        for uf in UFS:
            while True:
                lote = await pendentes(pool, uf, LOTE)
                if not lote:
                    break
                c = await carregar_lote(pool, uf, lote)
                for k in total:
                    total[k] += c[k]
                try:
                    await redis.set(HEARTBEAT, json.dumps({"ts": time.time(), "uf": uf, **total}), ex=INTERVALO * 3)
                except Exception:  # noqa: BLE001
                    pass
                print(f"[bu] lote {len(lote)} secoes | {c} | acumulado {total} | {time.monotonic() - inicio:.0f}s")
            val = await validar(pool, uf)
            print(f"[bu] validacao {uf.upper()} por cidade x cargo: {val}")
        try:
            await redis.set(HEARTBEAT, json.dumps({"ts": time.time(), **total}), ex=INTERVALO * 3)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(INTERVALO)


if __name__ == "__main__":
    asyncio.run(main())
