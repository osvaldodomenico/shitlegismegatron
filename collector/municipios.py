"""
Coletor por MUNICIPIO — grava no Postgres, em tempo real, o boletim de cada
cidade da UF para cada cargo, para apuracao e indicadores depois.

Fonte: o mesmo esquema `dados/<uf>/<uf><cod>-c<CCCC>-e<ELEICA>-u.json` do
collector principal, so que com o codigo TSE do municipio colado na UF
(ex.: sp71072 = Sao Paulo). A lista de municipios vem de
`<ELE>/config/mun-e<ELEICA>-cm.json`.

Decisoes de peso (VPS compartilhada com o BI do cliente, ~2 GB livres):
  - poucos downloads em paralelo (MUN_CONCURRENCY) e ciclo de 5 min;
  - If-None-Match: o TSE devolve 304 para arquivo que nao mudou — sem corpo;
  - no banco fica o ESTADO ATUAL de cada (cargo, municipio) como jsonb
    enxuto (candidatos com so os campos que importam) + uma serie leve de
    totais por ciclo. Explodir em uma linha por candidato (ate 1,3 mi de
    linhas por ciclo) seria pesado demais; a view `votos_municipio_candidato`
    faz isso sob demanda com jsonb_array_elements.

Nao toca no Redis de dados nem no collector principal: so escreve um
heartbeat proprio (`megatron:heartbeat:municipios`).
"""
import asyncio
import json
import os
import sys
import time
from typing import Optional

import asyncpg
import httpx
import redis.asyncio as aioredis

from fetcher import HEADERS
from tse_nested import achatar, tem_dado
from tse_urls import CARGO_CODIGOS, PATH_DADOS, SUFIXO

TSE_BASE_URL = os.environ.get("TSE_BASE_URL", "")
ELE = os.environ.get("ELE_1T", "")
POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

UF = os.environ.get("MUN_UF", "sp").strip().lower()
CARGOS = [c.strip() for c in os.environ.get(
    "MUN_CARGOS", "governador,senador,dep_federal,dep_estadual").split(",") if c.strip()]
INTERVALO = int(os.environ.get("MUN_INTERVAL_SECONDS", "300"))
CONCORRENCIA = int(os.environ.get("MUN_CONCURRENCY", "6"))

HEARTBEAT = "megatron:heartbeat:municipios"

# Campos do candidato que a apuracao posterior usa. O resto (datas, flags,
# vice/suplentes) so inflaria o jsonb de 645 cidades x 4 cargos.
CAMPOS_CAND = ("sqcand", "n", "nm", "nmu", "cc", "ccd", "vap", "pvap", "st", "dvt")


# ------------------------------------------------------------------ URLs

def url_config(base: str, ele: str) -> str:
    return f"{base}/{ele}/config/mun-e{str(ele).zfill(6)}-cm.json"


def url_municipio(base: str, ele: str, uf: str, cod: str, cargo: str) -> str:
    return (
        f"{base}/{ele}/{PATH_DADOS}/{uf}/"
        f"{uf}{cod}-c{CARGO_CODIGOS[cargo]}-e{str(ele).zfill(6)}-{SUFIXO}.json"
    )


def municipios_da_uf(cm: dict, uf: str) -> list[dict]:
    """Lista {cod, ibge, nome, capital} da UF a partir do mun-...-cm.json."""
    for abr in cm.get("abr") or []:
        if str(abr.get("cd", "")).lower() == uf:
            return [
                {
                    "cod": str(m.get("cd")),
                    "ibge": str(m.get("cdi") or ""),
                    "nome": str(m.get("nm") or ""),
                    "capital": str(m.get("c", "n")).lower() == "s",
                }
                for m in abr.get("mu") or []
            ]
    return []


# ------------------------------------------------------------ payload

def _int(v) -> int:
    try:
        return int(str(v or "0").replace(".", "").strip() or 0)
    except ValueError:
        return 0


def _num(v) -> float:
    try:
        return float(str(v or "0").replace(".", "").replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def enxugar(flat: dict) -> dict:
    """Payload plano reduzido ao que a analise por cidade precisa."""
    cands = [{k: c.get(k) for k in CAMPOS_CAND if k in c} for c in flat.get("cand") or []]
    return {
        "ele": flat.get("ele"), "cdabr": flat.get("cdabr"), "dg": flat.get("dg"), "hg": flat.get("hg"),
        "tf": flat.get("tf"), "pst": flat.get("pst"), "e": flat.get("e"), "v": flat.get("v"),
        "vv": flat.get("vv"), "vnom": flat.get("vnom"),
        "partidos": flat.get("partidos") or [],
        "vagas_por_agremiacao": flat.get("vagas_por_agremiacao") or {},
        "cand": cands,
    }


# ------------------------------------------------------------- banco

DDL = """
CREATE TABLE IF NOT EXISTS municipios (
    uf        TEXT NOT NULL,
    cod_tse   TEXT NOT NULL,
    cod_ibge  TEXT,
    nome      TEXT NOT NULL,
    capital   BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (uf, cod_tse)
);
CREATE TABLE IF NOT EXISTS votos_municipio (
    uf             TEXT NOT NULL,
    cargo          TEXT NOT NULL,
    cod_tse        TEXT NOT NULL,
    nome           TEXT NOT NULL,
    dg             TEXT,
    hg             TEXT,
    tf             TEXT,
    pst            NUMERIC(5,2),
    eleitores      BIGINT,
    total_votos    BIGINT,
    validos        BIGINT,
    nominais       BIGINT,
    etag           TEXT,
    payload        JSONB NOT NULL,
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uf, cargo, cod_tse)
);
CREATE TABLE IF NOT EXISTS votos_municipio_hist (
    time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uf        TEXT NOT NULL,
    cargo     TEXT NOT NULL,
    cod_tse   TEXT NOT NULL,
    hg        TEXT,
    pst       NUMERIC(5,2),
    validos   BIGINT,
    nominais  BIGINT
);
CREATE INDEX IF NOT EXISTS votos_municipio_hist_idx ON votos_municipio_hist (uf, cargo, cod_tse, time DESC);

-- Uma linha por candidato por cidade, explodida do jsonb sob demanda.
CREATE OR REPLACE VIEW votos_municipio_candidato AS
SELECT v.uf, v.cargo, v.cod_tse, v.nome AS municipio, v.pst, v.hg, v.tf,
       c->>'sqcand' AS sqcand, c->>'n' AS numero, c->>'nm' AS nome_candidato,
       c->>'nmu' AS nome_urna, c->>'cc' AS partido,
       NULLIF(regexp_replace(c->>'vap', '\\D', '', 'g'), '')::BIGINT AS votos,
       c->>'pvap' AS pct_validos, c->>'st' AS situacao, v.atualizado_em
FROM votos_municipio v, jsonb_array_elements(v.payload->'cand') AS c;

-- Totais por partido por cidade (nominais + legenda), tambem do jsonb.
CREATE OR REPLACE VIEW votos_municipio_partido AS
SELECT v.uf, v.cargo, v.cod_tse, v.nome AS municipio, v.pst, v.hg,
       p->>'n' AS numero, p->>'sg' AS partido,
       NULLIF(regexp_replace(p->>'tvtn', '\\D', '', 'g'), '')::BIGINT AS nominais,
       NULLIF(regexp_replace(p->>'tvtl', '\\D', '', 'g'), '')::BIGINT AS legenda,
       NULLIF(regexp_replace(p->>'tvan', '\\D', '', 'g'), '')::BIGINT AS total,
       v.atualizado_em
FROM votos_municipio v, jsonb_array_elements(v.payload->'partidos') AS p;
"""


async def preparar_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con:
        await con.execute(DDL)


async def gravar_municipios(pool: asyncpg.Pool, uf: str, lista: list[dict]) -> None:
    async with pool.acquire() as con:
        await con.executemany(
            """
            INSERT INTO municipios (uf, cod_tse, cod_ibge, nome, capital)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (uf, cod_tse) DO UPDATE
              SET cod_ibge = EXCLUDED.cod_ibge, nome = EXCLUDED.nome, capital = EXCLUDED.capital
            """,
            [(uf, m["cod"], m["ibge"], m["nome"], m["capital"]) for m in lista],
        )


async def carregar_etags(pool: asyncpg.Pool, uf: str) -> dict[tuple[str, str], str]:
    """Etags ja gravadas: depois de um restart, nao baixa de novo o que nao mudou."""
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT cargo, cod_tse, etag FROM votos_municipio WHERE uf = $1 AND etag IS NOT NULL", uf
        )
    return {(r["cargo"], r["cod_tse"]): r["etag"] for r in rows}


async def gravar_boletim(pool: asyncpg.Pool, uf: str, cargo: str, mun: dict, flat: dict, etag: Optional[str]) -> None:
    enx = enxugar(flat)
    pst = _num(flat.get("pst"))
    validos, nominais = _int(flat.get("vv")), _int(flat.get("vnom"))
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO votos_municipio
                    (uf, cargo, cod_tse, nome, dg, hg, tf, pst, eleitores, total_votos,
                     validos, nominais, etag, payload, atualizado_em)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,NOW())
                ON CONFLICT (uf, cargo, cod_tse) DO UPDATE SET
                    nome = EXCLUDED.nome, dg = EXCLUDED.dg, hg = EXCLUDED.hg, tf = EXCLUDED.tf,
                    pst = EXCLUDED.pst, eleitores = EXCLUDED.eleitores, total_votos = EXCLUDED.total_votos,
                    validos = EXCLUDED.validos, nominais = EXCLUDED.nominais, etag = EXCLUDED.etag,
                    payload = EXCLUDED.payload, atualizado_em = NOW()
                """,
                uf, cargo, mun["cod"], mun["nome"], flat.get("dg"), flat.get("hg"), flat.get("tf"),
                pst, _int(flat.get("e")), _int(flat.get("v")), validos, nominais, etag,
                json.dumps(enx, ensure_ascii=False),
            )
            await con.execute(
                """
                INSERT INTO votos_municipio_hist (uf, cargo, cod_tse, hg, pst, validos, nominais)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                uf, cargo, mun["cod"], flat.get("hg"), pst, validos, nominais,
            )


# ------------------------------------------------------------- coleta

async def coletar_um(client: httpx.AsyncClient, pool: asyncpg.Pool, sem: asyncio.Semaphore,
                     etags: dict, mun: dict, cargo: str) -> str:
    """Devolve 'novo' | 'igual' | 'vazio' | 'erro'."""
    chave = (cargo, mun["cod"])
    url = url_municipio(TSE_BASE_URL, ELE, UF, mun["cod"], cargo)
    headers = dict(HEADERS)
    if chave in etags:
        headers["If-None-Match"] = etags[chave]
    async with sem:
        try:
            r = await client.get(url, headers=headers, timeout=20)
            if r.status_code == 304:
                return "igual"
            r.raise_for_status()
            flat = achatar(r.json())
            if not tem_dado(flat):
                return "vazio"
            etag = r.headers.get("etag")
            await gravar_boletim(pool, UF, cargo, mun, flat, etag)
            if etag:
                etags[chave] = etag
            return "novo"
        except Exception as e:  # noqa: BLE001 — um municipio com erro nao derruba o ciclo
            print(f"[municipios] erro {cargo} {mun['cod']} {mun['nome']}: {e}", file=sys.stderr)
            return "erro"


async def ciclo(client: httpx.AsyncClient, pool: asyncpg.Pool, redis: aioredis.Redis,
                municipios: list[dict], etags: dict) -> None:
    inicio = time.monotonic()
    sem = asyncio.Semaphore(CONCORRENCIA)
    tarefas = [coletar_um(client, pool, sem, etags, m, c) for c in CARGOS for m in municipios]
    resultados = await asyncio.gather(*tarefas)
    contagem = {k: resultados.count(k) for k in ("novo", "igual", "vazio", "erro")}
    try:
        await redis.set(HEARTBEAT, json.dumps({"ts": time.time(), **contagem}), ex=INTERVALO * 3)
    except Exception as e:  # noqa: BLE001
        print(f"[municipios] heartbeat falhou: {e}", file=sys.stderr)
    print(f"[municipios] ciclo ok | arquivos={len(tarefas)} novos={contagem['novo']} "
          f"iguais={contagem['igual']} vazios={contagem['vazio']} erros={contagem['erro']} "
          f"| {time.monotonic() - inicio:.0f}s")


async def main() -> None:
    faltando = [n for n, v in (("TSE_BASE_URL", TSE_BASE_URL), ("ELE_1T", ELE),
                                ("POSTGRES_URL", POSTGRES_URL), ("REDIS_URL", REDIS_URL)) if not v]
    if faltando:
        print(f"[municipios] faltam variaveis: {', '.join(faltando)}", file=sys.stderr)
        sys.exit(1)

    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    redis = aioredis.from_url(REDIS_URL)
    await preparar_schema(pool)

    limites = httpx.Limits(max_connections=CONCORRENCIA, max_keepalive_connections=CONCORRENCIA)
    async with httpx.AsyncClient(limits=limites, http2=False) as client:
        r = await client.get(url_config(TSE_BASE_URL, ELE), headers=HEADERS, timeout=30)
        r.raise_for_status()
        municipios = municipios_da_uf(r.json(), UF)
        if not municipios:
            print(f"[municipios] nenhum municipio para a UF {UF!r} no config do TSE", file=sys.stderr)
            sys.exit(1)
        await gravar_municipios(pool, UF, municipios)
        etags = await carregar_etags(pool, UF)
        print(f"[municipios] {len(municipios)} municipios de {UF.upper()} x {len(CARGOS)} cargos, "
              f"a cada {INTERVALO}s, {CONCORRENCIA} em paralelo; {len(etags)} etags reaproveitadas")

        while True:
            await ciclo(client, pool, redis, municipios, etags)
            await asyncio.sleep(INTERVALO)


if __name__ == "__main__":
    asyncio.run(main())
