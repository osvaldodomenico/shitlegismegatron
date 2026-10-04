"""
Acesso ao banco (TimescaleDB / Postgres) via asyncpg.
get_pool() retorna pool compartilhado criado no startup da API.
Se POSTGRES_URL não estiver definido ou falhar, _pool fica None
e salvar_snapshot/buscar_historico viram no-op silencioso.
"""
import json
import os
from datetime import datetime
from typing import Optional, List
from zoneinfo import ZoneInfo

import asyncpg

_pool: Optional[asyncpg.Pool] = None
_db_disabled = False


async def get_pool() -> Optional[asyncpg.Pool]:
    """
    Retorna pool compartilhado. Se POSTGRES_URL ausente ou já tentou e falhou,
    retorna None e desativa persistência (modo 'no-DB').
    """
    global _pool, _db_disabled
    if _pool is not None:
        return _pool
    if _db_disabled:
        return None
    url = os.environ.get("POSTGRES_URL")
    if not url:
        print("[db] POSTGRES_URL ausente. Persistência desativada (modo no-DB).")
        _db_disabled = True
        return None
    try:
        _pool = await asyncpg.create_pool(dsn=url, min_size=1, max_size=5)
        print("[db] Pool Postgres conectado.")
        return _pool
    except Exception as e:
        print(f"[db] Falha ao conectar Postgres: {e}. Persistência desativada.")
        _db_disabled = True
        return None


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def salvar_snapshot(pool: Optional[asyncpg.Pool], uf: str, cargo: str, pst_pct: float, payload: dict) -> None:
    """INSERT na tabela snapshots. No-op se pool=None."""
    if pool is None:
        return
    try:
        await pool.execute(
            """
            INSERT INTO snapshots (uf, cargo, pst_pct, payload)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            uf, cargo, pst_pct, json.dumps(payload, ensure_ascii=False),
        )
    except Exception as e:
        print(f"[db] Erro ao salvar snapshot: {e}")


def inicio_do_dia_brasilia() -> datetime:
    """Meia-noite de hoje em Brasilia, com fuso — o inicio da apuracao do dia."""
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return agora.replace(hour=0, minute=0, second=0, microsecond=0)


async def buscar_historico(pool: Optional[asyncpg.Pool], uf: str, cargo: str, ultimas: int = 20) -> List[dict]:
    """
    Retorna série temporal SO DO DIA (Brasilia). Lista vazia se pool=None.

    A tabela guarda tambem os snapshots dos ensaios (dados de 2022 a 100%);
    sem este corte o grafico de evolucao comecava em 100% e caia para 0%.
    """
    if pool is None:
        return []
    try:
        rows = await pool.fetch(
            """
            SELECT time, pst_pct, payload
            FROM snapshots
            WHERE uf = $1 AND cargo = $2 AND time >= $4
            ORDER BY time DESC
            LIMIT $3
            """,
            uf, cargo, ultimas, inicio_do_dia_brasilia(),
        )
        return [
            {"time": str(row["time"]), "pst_pct": float(row["pst_pct"]), "payload": row["payload"]}
            for row in rows
        ]
    except Exception as e:
        print(f"[db] Erro ao buscar histórico: {e}")
        return []


async def buscar_selecao(
    pool: Optional[asyncpg.Pool], uf: str, cargo: str, perfil: str = "padrao"
) -> List[str]:
    """sqcands acompanhados nessa corrida/perfil. Lista vazia se pool=None ou sem linha."""
    if pool is None:
        return []
    try:
        row = await pool.fetchrow(
            "SELECT sqcands FROM selecao WHERE uf = $1 AND cargo = $2 AND perfil = $3",
            uf, cargo, perfil,
        )
        return list(row["sqcands"]) if row else []
    except Exception as e:
        print(f"[db] Erro ao buscar selecao: {e}")
        return []


async def salvar_selecao(
    pool: Optional[asyncpg.Pool], uf: str, cargo: str, sqcands: List[str],
    perfil: str = "padrao",
) -> bool:
    """
    Grava a selecao da corrida. Retorna False se a persistencia esta desativada,
    para a rota poder avisar que a escolha nao sobrevive a um restart.
    """
    if pool is None:
        return False
    try:
        await pool.execute(
            """
            INSERT INTO selecao (uf, cargo, perfil, sqcands, atualizado_em)
            VALUES ($1, $2, $4, $3, NOW())
            ON CONFLICT (uf, cargo, perfil)
            DO UPDATE SET sqcands = EXCLUDED.sqcands, atualizado_em = NOW()
            """,
            uf, cargo, sqcands, perfil,
        )
        return True
    except Exception as e:
        print(f"[db] Erro ao salvar selecao: {e}")
        return False


async def carregar_todas_selecoes(pool: Optional[asyncpg.Pool]) -> List[dict]:
    """Todas as selecoes, para reidratar o cache em memoria no startup da API."""
    if pool is None:
        return []
    try:
        rows = await pool.fetch("SELECT uf, cargo, perfil, sqcands FROM selecao")
        return [
            {"uf": r["uf"], "cargo": r["cargo"], "perfil": r["perfil"], "sqcands": list(r["sqcands"])}
            for r in rows
        ]
    except Exception as e:
        print(f"[db] Erro ao carregar selecoes: {e}")
        return []


async def buscar_votos_por_cidade(
    pool: Optional[asyncpg.Pool], uf: str, cargo: str, sqcand: str, nivel: str = "municipio"
) -> List[dict]:
    """
    Votos de um candidato em cada cidade (ou zona) da corrida, do mais votado
    para o menos. Explode o jsonb de `votos_municipio` sob demanda (~0,5 s em
    645 cidades). Lista vazia se pool=None ou se o coletor ainda nao gravou.
    """
    if pool is None:
        return []
    try:
        rows = await pool.fetch(
            """
            SELECT v.cod_tse, v.cod_zona, v.nome, v.pst, v.validos, v.hg, v.atualizado_em,
                   COALESCE(NULLIF(regexp_replace(c->>'vap', '\\D', '', 'g'), '')::BIGINT, 0) AS votos,
                   c->>'pvap' AS pct
            FROM votos_municipio v, jsonb_array_elements(v.payload->'cand') AS c
            WHERE v.uf = $1 AND v.cargo = $2 AND v.nivel = $3 AND c->>'sqcand' = $4
            ORDER BY votos DESC, v.nome
            """,
            uf, cargo, nivel, str(sqcand),
        )
        return [
            {
                "cod": r["cod_tse"], "zona": r["cod_zona"], "nome": r["nome"],
                "pst": float(r["pst"] or 0), "validos": int(r["validos"] or 0), "hg": r["hg"],
                "votos": int(r["votos"] or 0), "pct": r["pct"] or "0,00",
                "atualizado_em": str(r["atualizado_em"]),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[db] Erro ao buscar votos por cidade: {e}")
        return []
