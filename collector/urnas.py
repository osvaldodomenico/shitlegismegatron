"""
Coletor de BOLETINS DE URNA por SECAO — baixa, para cada secao eleitoral da
UF, tudo que o TSE publica da urna (bu, imgbu, rdv, vota, log) e indexa no
Postgres, com os bytes no disco da VPS.

Fonte (confirmada em 04/10/2026, pleito 3220):
    <base>/arquivo-urna/<PLEITO>/dados/<uf>/<mun>/<zona>/<secao>/
        p00<PLEITO>-<uf>-m<mun>-z<zona>-s<secao>-aux.json   -> indice da secao
        <hash-hex>/<nome do arquivo>                        -> os arquivos
O `hash` do aux e usado EM HEXADECIMAL como diretorio (decodifica-lo da 403).
Nomes: o0<PLEITO><uf><mun><zona><secao>-{bu,imgbu,rdv,log}.dat / -vota.vsc.

O universo de secoes vem da tabela `locais_votacao` (cadastro do TSE), que
tambem da escola, endereco e bairro de cada secao — e o que permite agregar
votos por escola/bairro depois.

Fases (URNA_FASES, separadas por "|"): primeiro os boletins (bu, imgbu) de
TODAS as secoes, depois o resto (rdv, vota, log). Cada arquivo e baixado uma
vez: o indice no banco diz o que ja esta no disco. Secao "nao recebida" ou
sem urna (secao agregada) e revisitada a cada varredura.

Decisoes de peso: concorrencia baixa (VPS compartilhada), bytes no DISCO e
nao no banco (SP ~ 23 GB), heartbeat proprio (`megatron:heartbeat:urnas`).
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import asyncpg
import httpx
import redis.asyncio as aioredis

from fetcher import HEADERS

TSE_BASE_URL = os.environ.get("TSE_BASE_URL", "")
PLEITO = os.environ.get("URNA_PLEITO", "")
POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

UFS = [u.strip().lower() for u in os.environ.get("URNA_UFS", "sp").split(",") if u.strip()]
DIR = Path(os.environ.get("URNA_DIR", "/dados/urnas"))
CONCORRENCIA = int(os.environ.get("URNA_CONCURRENCY", "8"))
INTERVALO = int(os.environ.get("URNA_INTERVAL_SECONDS", "1800"))
FASES = [[t.strip() for t in f.split(",") if t.strip()]
         for f in os.environ.get("URNA_FASES", "bu,imgbu|rdv,vota,log").split("|")]

HEARTBEAT = "megatron:heartbeat:urnas"


# ------------------------------------------------------------------ URLs

def _z(v, n) -> str:
    return str(int(v)).zfill(n)


def url_aux(base: str, pleito: str, uf: str, mun: str, zona, secao) -> str:
    p = str(pleito).zfill(5)
    return (f"{base}/arquivo-urna/{int(pleito)}/dados/{uf}/{_z(mun, 5)}/{_z(zona, 4)}/{_z(secao, 4)}/"
            f"p{p}-{uf}-m{_z(mun, 5)}-z{_z(zona, 4)}-s{_z(secao, 4)}-aux.json")


def url_arquivo(base: str, pleito: str, uf: str, mun: str, zona, secao, hash_hex: str, nome: str) -> str:
    return (f"{base}/arquivo-urna/{int(pleito)}/dados/{uf}/{_z(mun, 5)}/{_z(zona, 4)}/{_z(secao, 4)}/"
            f"{hash_hex}/{nome}")


def caminho_local(raiz: Path, uf: str, mun: str, zona, secao, nome: str) -> Path:
    return raiz / uf / _z(mun, 5) / _z(zona, 4) / _z(secao, 4) / nome


def arquivos_do_aux(aux: dict) -> tuple[Optional[str], list[dict]]:
    """(hash_hex, [{tipo, nome}]) do primeiro bloco de hashes do indice."""
    blocos = aux.get("hashes") or []
    if not blocos:
        return None, []
    h = blocos[0]
    return h.get("hash"), [{"tipo": a.get("tp"), "nome": a.get("nm")} for a in (h.get("arq") or []) if a.get("nm")]


# ------------------------------------------------------------- banco

DDL = """
CREATE TABLE IF NOT EXISTS urna_secao (
    uf           TEXT NOT NULL,
    cod_mun      TEXT NOT NULL,
    zona         INT  NOT NULL,
    secao        INT  NOT NULL,
    pleito       TEXT,
    st           TEXT,                 -- situacao no indice do TSE ("Recebida", ...)
    hash         TEXT,
    dr           TEXT, hr TEXT,        -- data/hora de recebimento no TSE
    aux          JSONB,                -- indice completo da secao
    arquivos     JSONB NOT NULL DEFAULT '{}'::jsonb,   -- tipo -> {nome, bytes, caminho}
    sem_urna     BOOLEAN NOT NULL DEFAULT FALSE,       -- aux 404: secao agregada ou nao recebida
    tentativas   INT NOT NULL DEFAULT 0,
    erro         TEXT,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uf, cod_mun, zona, secao)
);
CREATE INDEX IF NOT EXISTS urna_secao_st_idx ON urna_secao (uf, st);
"""


async def preparar_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as con:
        await con.execute(DDL)


async def secoes_da_uf(pool: asyncpg.Pool, uf: str) -> list[tuple[str, int, int]]:
    """Universo: toda secao do cadastro de locais de votacao da UF."""
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT DISTINCT cd_municipio, nr_zona, nr_secao FROM locais_votacao "
            "WHERE upper(sg_uf) = $1 ORDER BY 1, 2, 3", uf.upper()
        )
    return [(r["cd_municipio"], int(r["nr_zona"]), int(r["nr_secao"])) for r in rows]


async def estado_atual(pool: asyncpg.Pool, uf: str) -> dict[tuple[str, int, int], dict]:
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT cod_mun, zona, secao, hash, arquivos, sem_urna, st FROM urna_secao WHERE uf = $1", uf
        )
    return {(r["cod_mun"], r["zona"], r["secao"]): {
        "hash": r["hash"], "arquivos": json.loads(r["arquivos"]) if isinstance(r["arquivos"], str) else (r["arquivos"] or {}),
        "sem_urna": r["sem_urna"], "st": r["st"],
    } for r in rows}


async def gravar(pool: asyncpg.Pool, uf: str, mun: str, zona: int, secao: int, **campos) -> None:
    cols = ["uf", "cod_mun", "zona", "secao"] + list(campos.keys())
    vals = [uf, mun, zona, secao] + [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in campos.values()]
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in campos.keys()) + ", atualizado_em = NOW()"
    marcadores = ", ".join(f"${i + 1}" + ("::jsonb" if isinstance(campos.get(c), (dict, list)) else "") for i, c in enumerate(cols))
    async with pool.acquire() as con:
        await con.execute(
            f"INSERT INTO urna_secao ({', '.join(cols)}) VALUES ({marcadores}) "
            f"ON CONFLICT (uf, cod_mun, zona, secao) DO UPDATE SET {sets}", *vals
        )


# ------------------------------------------------------------- coleta

async def baixar(client: httpx.AsyncClient, url: str) -> Optional[bytes]:
    r = await client.get(url, headers=HEADERS, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


async def coletar_secao(client: httpx.AsyncClient, pool: asyncpg.Pool, sem: asyncio.Semaphore,
                        uf: str, mun: str, zona: int, secao: int, atual: Optional[dict], tipos: list[str]) -> str:
    """
    Garante os arquivos dos `tipos` desta secao. Devolve:
      'completo' (nada a fazer) | 'baixado' | 'sem_urna' | 'parcial' | 'erro'
    """
    async with sem:
        try:
            ja = (atual or {}).get("arquivos") or {}
            if atual and atual.get("hash") and all(t in ja for t in tipos if t in ("bu", "rdv", "vota", "log")) \
               and ("imgbu" not in tipos or "imgbu" in ja):
                return "completo"

            # Indice: so rebaixa se ainda nao temos hash (ou se faltam arquivos
            # que o indice pode ter ganho desde entao, como o imgbu).
            aux_bytes = await baixar(client, url_aux(TSE_BASE_URL, PLEITO, uf, mun, zona, secao))
            if aux_bytes is None:
                await gravar(pool, uf, mun, zona, secao, pleito=PLEITO, sem_urna=True,
                             tentativas=((atual or {}).get("tentativas") or 0) + 1)
                return "sem_urna"
            aux = json.loads(aux_bytes)
            hash_hex, lista = arquivos_do_aux(aux)
            bloco = (aux.get("hashes") or [{}])[0]
            if not hash_hex:
                await gravar(pool, uf, mun, zona, secao, pleito=PLEITO, st=aux.get("st"), aux=aux, sem_urna=False)
                return "parcial"

            arquivos = dict(ja) if ja and atual.get("hash") == hash_hex else {}
            faltou = False
            for a in lista:
                tipo, nome = a["tipo"], a["nome"]
                if tipo not in tipos or tipo in arquivos:
                    continue
                dados = await baixar(client, url_arquivo(TSE_BASE_URL, PLEITO, uf, mun, zona, secao, hash_hex, nome))
                if dados is None:            # listado no indice mas ainda nao publicado (imgbu demora)
                    faltou = True
                    continue
                destino = caminho_local(DIR, uf, mun, zona, secao, nome)
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(dados)
                arquivos[tipo] = {"nome": nome, "bytes": len(dados), "caminho": str(destino)}

            await gravar(pool, uf, mun, zona, secao, pleito=PLEITO, st=aux.get("st"), hash=hash_hex,
                         dr=bloco.get("dr"), hr=bloco.get("hr"), aux=aux, arquivos=arquivos, sem_urna=False, erro=None)
            return "parcial" if faltou else "baixado"
        except Exception as e:  # noqa: BLE001 — uma secao com erro nao derruba a varredura
            try:
                await gravar(pool, uf, mun, zona, secao, pleito=PLEITO, erro=str(e)[:300],
                             tentativas=((atual or {}).get("tentativas") or 0) + 1)
            except Exception:  # noqa: BLE001
                pass
            return "erro"


async def varredura(client: httpx.AsyncClient, pool: asyncpg.Pool, redis: aioredis.Redis) -> None:
    inicio = time.monotonic()
    total = {"completo": 0, "baixado": 0, "sem_urna": 0, "parcial": 0, "erro": 0}
    for uf in UFS:
        secoes = await secoes_da_uf(pool, uf)
        for fase, tipos in enumerate(FASES, 1):
            atual = await estado_atual(pool, uf)
            sem = asyncio.Semaphore(CONCORRENCIA)
            print(f"[urnas] {uf.upper()} fase {fase} ({','.join(tipos)}): {len(secoes)} secoes")
            # Lotes para nao criar 100 mil corrotinas de uma vez.
            for i in range(0, len(secoes), 500):
                lote = secoes[i:i + 500]
                res = await asyncio.gather(*(
                    coletar_secao(client, pool, sem, uf, m, z, s, atual.get((m, z, s)), tipos) for (m, z, s) in lote
                ))
                for r_ in res:
                    total[r_] += 1
                try:
                    await redis.set(HEARTBEAT, json.dumps({"ts": time.time(), "uf": uf, "fase": fase,
                                                           "progresso": i + len(lote), "secoes": len(secoes), **total}),
                                    ex=INTERVALO * 3)
                except Exception:  # noqa: BLE001
                    pass
                if (i // 500) % 20 == 0:
                    print(f"[urnas] {uf.upper()} fase {fase}: {i + len(lote)}/{len(secoes)} | {total} | {time.monotonic() - inicio:.0f}s")
    print(f"[urnas] varredura ok | {total} | {time.monotonic() - inicio:.0f}s")


async def main() -> None:
    faltando = [n for n, v in (("TSE_BASE_URL", TSE_BASE_URL), ("URNA_PLEITO", PLEITO),
                                ("POSTGRES_URL", POSTGRES_URL), ("REDIS_URL", REDIS_URL)) if not v]
    if faltando:
        print(f"[urnas] faltam variaveis: {', '.join(faltando)}", file=sys.stderr)
        sys.exit(1)
    DIR.mkdir(parents=True, exist_ok=True)
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
    redis = aioredis.from_url(REDIS_URL)
    await preparar_schema(pool)
    limites = httpx.Limits(max_connections=CONCORRENCIA, max_keepalive_connections=CONCORRENCIA)
    async with httpx.AsyncClient(limits=limites, http2=False) as client:
        while True:
            await varredura(client, pool, redis)
            await asyncio.sleep(INTERVALO)


if __name__ == "__main__":
    asyncio.run(main())
