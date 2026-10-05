"""
Coletor TERRITORIAL — grava no Postgres, em tempo real, tudo que o TSE
publica por abrangencia: cada cidade e cada zona eleitoral da UF (todos os
cargos, presidente incluido), cada UF (presidente) e o Brasil (presidente),
para apuracao e indicadores depois.

Fonte: o mesmo esquema `dados/<abr>/<abr>-c<CCCC>-e<ELEICA>-u.json` do
collector principal. Abrangencias:
    uf        sp-c0003-e006259           (estado)
    municipio sp71072-c0006-e006259      (codigo TSE da cidade colado na UF)
    zona      sp71072-z0020-c0006-...    (zona dentro da cidade)
    br        br-c0001-e006257           (presidente, nacional)
Presidente usa o codigo de eleicao NACIONAL (ELE_1T_BR); os demais, o da UF
(ELE_1T). A lista de municipios/zonas vem de `<ELE>/config/mun-e<ELEICA>-cm.json`.
Abaixo da zona (secao / boletim de urna) o TSE serve so o indice; os
arquivos respondem 403/404 — fora daqui.

Decisoes de peso (VPS compartilhada com o BI do cliente, ~2 GB livres):
  - poucos downloads em paralelo (MUN_CONCURRENCY) e ciclo de 5 min;
  - If-None-Match: o TSE devolve 304 para arquivo que nao mudou — sem corpo;
  - no banco fica o ESTADO ATUAL de cada (nivel, cargo, lugar) como jsonb
    enxuto: candidatos com os campos que importam, partidos, vagas por
    agremiacao, federacoes e os blocos de TOTAIS do TSE (secoes, eleitorado,
    comparecimento, abstencao, brancos, nulos) + uma serie leve por ciclo.
    As views `votos_municipio_candidato`, `_partido` e `_totais` explodem
    isso sob demanda.

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
ELE_BR = os.environ.get("ELE_1T_BR") or ELE
POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

UF = os.environ.get("MUN_UF", "sp").strip().lower()
CARGOS = [c.strip() for c in os.environ.get(
    "MUN_CARGOS", "presidente,governador,senador,dep_federal,dep_estadual").split(",") if c.strip()]
INTERVALO = int(os.environ.get("MUN_INTERVAL_SECONDS", "300"))
CONCORRENCIA = int(os.environ.get("MUN_CONCURRENCY", "8"))
# Niveis: municipio e zona (todos os CARGOS na UF), uf (presidente em TODAS
# as UFs + os cargos estaduais da propria UF) e br (presidente nacional).
NIVEIS = [n.strip() for n in os.environ.get("MUN_NIVEIS", "municipio,zona,uf,br").split(",") if n.strip()]

CARGOS_NACIONAIS = frozenset({"presidente"})
HEARTBEAT = "megatron:heartbeat:municipios"

# Campos do candidato que a apuracao posterior usa. O resto (datas, flags,
# vice/suplentes) so inflaria o jsonb de 645 cidades x 5 cargos.
CAMPOS_CAND = ("sqcand", "n", "nm", "nmu", "cc", "ccd", "vap", "pvap", "st", "dvt")


def ele_de(cargo: str) -> str:
    return ELE_BR if cargo in CARGOS_NACIONAIS else ELE


# ------------------------------------------------------------------ URLs

def url_config(base: str, ele: str) -> str:
    return f"{base}/{ele}/config/mun-e{str(ele).zfill(6)}-cm.json"


def url_municipio(base: str, ele: str, uf: str, cod: str, cargo: str, zona: str = "") -> str:
    """Sem `zona` e o arquivo da cidade; com `zona` ("0020") e o da zona dentro dela."""
    z = f"-z{str(zona).zfill(4)}" if zona else ""
    return (
        f"{base}/{ele}/{PATH_DADOS}/{uf}/"
        f"{uf}{cod}{z}-c{CARGO_CODIGOS[cargo]}-e{str(ele).zfill(6)}-{SUFIXO}.json"
    )


def url_abrangencia(base: str, ele: str, abr: str, cargo: str) -> str:
    """Arquivo de uma UF ("sp") ou do Brasil ("br")."""
    return (
        f"{base}/{ele}/{PATH_DADOS}/{abr}/"
        f"{abr}-c{CARGO_CODIGOS[cargo]}-e{str(ele).zfill(6)}-{SUFIXO}.json"
    )


def tarefas_de(municipios: list[dict], cargos: list[str], niveis: list[str],
               uf: str = "sp", ufs: Optional[list[str]] = None, ele: str = "", ele_br: str = "") -> list[dict]:
    """
    Uma tarefa por arquivo: {nivel, uf, cod, zona, cargo, nome, url_ele}.
      municipio/zona: cada cidade (e zona) da UF, para cada cargo.
      uf: presidente em todas as UFs + cargos estaduais da propria UF.
      br: presidente nacional.
    """
    ele_br = ele_br or ele
    saida: list[dict] = []
    for cargo in cargos:
        e = ele_br if cargo in CARGOS_NACIONAIS else ele
        for m in municipios:
            if "municipio" in niveis:
                saida.append({"nivel": "municipio", "uf": uf, "cod": m["cod"], "zona": "", "cargo": cargo, "nome": m["nome"], "ele": e})
            if "zona" in niveis:
                for z in m.get("zonas") or []:
                    saida.append({"nivel": "zona", "uf": uf, "cod": m["cod"], "zona": z, "cargo": cargo, "nome": m["nome"], "ele": e})
        if "uf" in niveis:
            abrs = (ufs or [uf]) if cargo in CARGOS_NACIONAIS else [uf]
            for a in abrs:
                saida.append({"nivel": "uf", "uf": a, "cod": a, "zona": "", "cargo": cargo, "nome": a.upper(), "ele": e})
        if "br" in niveis and cargo in CARGOS_NACIONAIS:
            saida.append({"nivel": "br", "uf": "br", "cod": "br", "zona": "", "cargo": cargo, "nome": "BRASIL", "ele": e})
    return saida


def url_da(base: str, t: dict) -> str:
    if t["nivel"] in ("uf", "br"):
        return url_abrangencia(base, t["ele"], t["cod"], t["cargo"])
    return url_municipio(base, t["ele"], t["uf"], t["cod"], t["cargo"], t["zona"])


def municipios_da_uf(cm: dict, uf: str) -> list[dict]:
    """Lista {cod, ibge, nome, capital, zonas} da UF a partir do mun-...-cm.json."""
    for abr in cm.get("abr") or []:
        if str(abr.get("cd", "")).lower() == uf:
            return [
                {
                    "cod": str(m.get("cd")),
                    "ibge": str(m.get("cdi") or ""),
                    "nome": str(m.get("nm") or ""),
                    "capital": str(m.get("c", "n")).lower() == "s",
                    "zonas": [str(z).zfill(4) for z in (m.get("z") or [])],
                }
                for m in abr.get("mu") or []
            ]
    return []


def ufs_do_config(cm: dict) -> list[str]:
    """Siglas das UFs no config (27, 'zz' = exterior fica de fora)."""
    return sorted({str(a.get("cd", "")).lower() for a in cm.get("abr") or []} - {"", "zz", "br"})


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


def enxugar(flat: dict, bruto: Optional[dict] = None) -> dict:
    """
    Payload plano reduzido ao que a analise precisa — MAIS os blocos de totais
    do arquivo original (`s` secoes, `e` eleitorado/comparecimento/abstencao,
    `v` votos validos/brancos/nulos/legenda) e as federacoes, que o achatador
    nao preserva.
    """
    bruto = bruto or {}
    cands = [{k: c.get(k) for k in CAMPOS_CAND if k in c} for c in flat.get("cand") or []]
    cargos = bruto.get("carg") or []
    return {
        "ele": flat.get("ele"), "tpabr": flat.get("tpabr"), "cdabr": flat.get("cdabr"),
        "dg": flat.get("dg"), "hg": flat.get("hg"), "tf": flat.get("tf"),
        "pst": flat.get("pst"), "e": flat.get("e"), "v": flat.get("v"), "tv": flat.get("tv"),
        "vv": flat.get("vv"), "vnom": flat.get("vnom"),
        "totais": {"s": bruto.get("s") or {}, "e": bruto.get("e") or {}, "v": bruto.get("v") or {}},
        "federacoes": [f for c in cargos for f in (c.get("fed") or [])],
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
CREATE TABLE IF NOT EXISTS zonas (
    uf        TEXT NOT NULL,
    cod_zona  TEXT NOT NULL,
    cod_tse   TEXT NOT NULL,   -- municipio
    PRIMARY KEY (uf, cod_zona, cod_tse)
);
CREATE TABLE IF NOT EXISTS votos_municipio (
    uf             TEXT NOT NULL,
    cargo          TEXT NOT NULL,
    cod_tse        TEXT NOT NULL,
    nivel          TEXT NOT NULL DEFAULT 'municipio',
    cod_zona       TEXT NOT NULL DEFAULT '',
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
    PRIMARY KEY (uf, cargo, cod_tse, cod_zona)
);
CREATE TABLE IF NOT EXISTS votos_municipio_hist (
    time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uf        TEXT NOT NULL,
    cargo     TEXT NOT NULL,
    cod_tse   TEXT NOT NULL,
    cod_zona  TEXT NOT NULL DEFAULT '',
    hg        TEXT,
    pst       NUMERIC(5,2),
    validos   BIGINT,
    nominais  BIGINT
);
-- Migracao da versao so-municipio (04/10 19h): acrescenta nivel/cod_zona e
-- amplia a chave. Idempotente.
ALTER TABLE votos_municipio ADD COLUMN IF NOT EXISTS nivel TEXT NOT NULL DEFAULT 'municipio';
ALTER TABLE votos_municipio ADD COLUMN IF NOT EXISTS cod_zona TEXT NOT NULL DEFAULT '';
ALTER TABLE votos_municipio_hist ADD COLUMN IF NOT EXISTS cod_zona TEXT NOT NULL DEFAULT '';
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.conrelid = 'votos_municipio'::regclass AND c.contype = 'p' AND a.attname = 'cod_zona'
    ) THEN
        ALTER TABLE votos_municipio DROP CONSTRAINT IF EXISTS votos_municipio_pkey;
        ALTER TABLE votos_municipio ADD PRIMARY KEY (uf, cargo, cod_tse, cod_zona);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS votos_municipio_hist_idx ON votos_municipio_hist (uf, cargo, cod_tse, cod_zona, time DESC);

-- Uma linha por candidato por lugar, explodida do jsonb sob demanda.
DROP VIEW IF EXISTS votos_municipio_candidato;
CREATE VIEW votos_municipio_candidato AS
SELECT v.uf, v.cargo, v.nivel, v.cod_tse, v.cod_zona, v.nome AS municipio, v.pst, v.hg, v.tf,
       c->>'sqcand' AS sqcand, c->>'n' AS numero, c->>'nm' AS nome_candidato,
       c->>'nmu' AS nome_urna, c->>'cc' AS partido,
       NULLIF(regexp_replace(c->>'vap', '\\D', '', 'g'), '')::BIGINT AS votos,
       c->>'pvap' AS pct_validos, c->>'st' AS situacao, v.atualizado_em
FROM votos_municipio v, jsonb_array_elements(v.payload->'cand') AS c;

-- Totais por partido por lugar (nominais + legenda), tambem do jsonb.
DROP VIEW IF EXISTS votos_municipio_partido;
CREATE VIEW votos_municipio_partido AS
SELECT v.uf, v.cargo, v.nivel, v.cod_tse, v.cod_zona, v.nome AS municipio, v.pst, v.hg,
       p->>'n' AS numero, p->>'sg' AS partido,
       NULLIF(regexp_replace(p->>'tvtn', '\\D', '', 'g'), '')::BIGINT AS nominais,
       NULLIF(regexp_replace(p->>'tvtl', '\\D', '', 'g'), '')::BIGINT AS legenda,
       NULLIF(regexp_replace(p->>'tvan', '\\D', '', 'g'), '')::BIGINT AS total,
       v.atualizado_em
FROM votos_municipio v, jsonb_array_elements(v.payload->'partidos') AS p;

-- Totais da corrida em cada lugar: secoes, eleitorado, comparecimento,
-- abstencao, validos, brancos, nulos (blocos s/e/v do arquivo do TSE).
DROP VIEW IF EXISTS votos_municipio_totais;
CREATE VIEW votos_municipio_totais AS
SELECT v.uf, v.cargo, v.nivel, v.cod_tse, v.cod_zona, v.nome AS municipio, v.pst, v.hg, v.tf,
       NULLIF(regexp_replace(v.payload->'totais'->'s'->>'ts', '\\D', '', 'g'), '')::BIGINT AS secoes,
       NULLIF(regexp_replace(v.payload->'totais'->'s'->>'st', '\\D', '', 'g'), '')::BIGINT AS secoes_totalizadas,
       NULLIF(regexp_replace(v.payload->'totais'->'e'->>'te', '\\D', '', 'g'), '')::BIGINT AS eleitores_aptos,
       NULLIF(regexp_replace(v.payload->'totais'->'e'->>'c',  '\\D', '', 'g'), '')::BIGINT AS comparecimento,
       NULLIF(regexp_replace(v.payload->'totais'->'e'->>'a',  '\\D', '', 'g'), '')::BIGINT AS abstencao,
       v.payload->'totais'->'e'->>'pa' AS pct_abstencao,
       NULLIF(regexp_replace(v.payload->'totais'->'v'->>'tv', '\\D', '', 'g'), '')::BIGINT AS total_votos,
       NULLIF(regexp_replace(v.payload->'totais'->'v'->>'vv', '\\D', '', 'g'), '')::BIGINT AS validos,
       NULLIF(regexp_replace(v.payload->'totais'->'v'->>'vnom', '\\D', '', 'g'), '')::BIGINT AS nominais,
       NULLIF(regexp_replace(v.payload->'totais'->'v'->>'vb', '\\D', '', 'g'), '')::BIGINT AS brancos,
       v.payload->'totais'->'v'->>'pvb' AS pct_brancos,
       NULLIF(regexp_replace(v.payload->'totais'->'v'->>'tvn', '\\D', '', 'g'), '')::BIGINT AS nulos,
       v.payload->'totais'->'v'->>'ptvn' AS pct_nulos,
       v.atualizado_em
FROM votos_municipio v;
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
        await con.executemany(
            """
            INSERT INTO zonas (uf, cod_zona, cod_tse) VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            [(uf, z, m["cod"]) for m in lista for z in m.get("zonas") or []],
        )


async def carregar_etags(pool: asyncpg.Pool) -> dict[tuple[str, str, str, str], str]:
    """
    Etags ja gravadas: depois de um restart, nao baixa de novo o que nao mudou.
    So valem linhas ja no formato atual (com `totais`): linha antiga precisa
    ser rebaixada uma vez para ganhar os blocos novos.
    """
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT uf, cargo, cod_tse, cod_zona, etag FROM votos_municipio "
            "WHERE etag IS NOT NULL AND payload ? 'totais'"
        )
    return {(r["uf"], r["cargo"], r["cod_tse"], r["cod_zona"]): r["etag"] for r in rows}


async def gravar_boletim(pool: asyncpg.Pool, t: dict, flat: dict, bruto: dict, etag: Optional[str]) -> None:
    enx = enxugar(flat, bruto)
    pst = _num(flat.get("pst"))
    validos, nominais = _int(flat.get("vv")), _int(flat.get("vnom"))
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO votos_municipio
                    (uf, cargo, cod_tse, nivel, cod_zona, nome, dg, hg, tf, pst, eleitores, total_votos,
                     validos, nominais, etag, payload, atualizado_em)
                VALUES ($1,$2,$3,$15,$16,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,NOW())
                ON CONFLICT (uf, cargo, cod_tse, cod_zona) DO UPDATE SET
                    nivel = EXCLUDED.nivel, nome = EXCLUDED.nome, dg = EXCLUDED.dg, hg = EXCLUDED.hg, tf = EXCLUDED.tf,
                    pst = EXCLUDED.pst, eleitores = EXCLUDED.eleitores, total_votos = EXCLUDED.total_votos,
                    validos = EXCLUDED.validos, nominais = EXCLUDED.nominais, etag = EXCLUDED.etag,
                    payload = EXCLUDED.payload, atualizado_em = NOW()
                """,
                t["uf"], t["cargo"], t["cod"], t["nome"], flat.get("dg"), flat.get("hg"), flat.get("tf"),
                pst, _int(flat.get("e")), _int(flat.get("tv")), validos, nominais, etag,
                json.dumps(enx, ensure_ascii=False), t["nivel"], t["zona"],
            )
            await con.execute(
                """
                INSERT INTO votos_municipio_hist (uf, cargo, cod_tse, cod_zona, hg, pst, validos, nominais)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                t["uf"], t["cargo"], t["cod"], t["zona"], flat.get("hg"), pst, validos, nominais,
            )


# ------------------------------------------------------------- coleta

async def coletar_um(client: httpx.AsyncClient, pool: asyncpg.Pool, sem: asyncio.Semaphore,
                     etags: dict, t: dict) -> str:
    """Devolve 'novo' | 'igual' | 'vazio' | 'erro'."""
    chave = (t["uf"], t["cargo"], t["cod"], t["zona"])
    url = url_da(TSE_BASE_URL, t)
    headers = dict(HEADERS)
    if chave in etags:
        headers["If-None-Match"] = etags[chave]
    async with sem:
        try:
            r = await client.get(url, headers=headers, timeout=20)
            if r.status_code == 304:
                return "igual"
            r.raise_for_status()
            bruto = r.json()
            flat = achatar(bruto)
            if not tem_dado(flat):
                return "vazio"
            etag = r.headers.get("etag")
            await gravar_boletim(pool, t, flat, bruto, etag)
            if etag:
                etags[chave] = etag
            return "novo"
        except Exception as e:  # noqa: BLE001 — um lugar com erro nao derruba o ciclo
            print(f"[municipios] erro {t['nivel']} {t['cargo']} {t['uf']}{t['cod']}"
                  f"{'-z' + t['zona'] if t['zona'] else ''} {t['nome']}: {e}", file=sys.stderr)
            return "erro"


async def ciclo(client: httpx.AsyncClient, pool: asyncpg.Pool, redis: aioredis.Redis,
                tarefas_lista: list[dict], etags: dict) -> None:
    inicio = time.monotonic()
    sem = asyncio.Semaphore(CONCORRENCIA)
    tarefas = [coletar_um(client, pool, sem, etags, t) for t in tarefas_lista]
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
        cm = r.json()
        municipios = municipios_da_uf(cm, UF)
        if not municipios:
            print(f"[municipios] nenhum municipio para a UF {UF!r} no config do TSE", file=sys.stderr)
            sys.exit(1)
        ufs = ufs_do_config(cm)
        await gravar_municipios(pool, UF, municipios)
        etags = await carregar_etags(pool)
        tarefas_lista = tarefas_de(municipios, CARGOS, NIVEIS, UF, ufs, ELE, ELE_BR)
        zonas = sum(len(m["zonas"]) for m in municipios)
        print(f"[municipios] {len(municipios)} municipios ({zonas} zonas) de {UF.upper()}, {len(ufs)} UFs, "
              f"cargos={','.join(CARGOS)}, niveis={','.join(NIVEIS)} -> {len(tarefas_lista)} arquivos/ciclo, "
              f"a cada {INTERVALO}s, {CONCORRENCIA} em paralelo; {len(etags)} etags reaproveitadas")

        while True:
            await ciclo(client, pool, redis, tarefas_lista, etags)
            await asyncio.sleep(INTERVALO)


if __name__ == "__main__":
    asyncio.run(main())
