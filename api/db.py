"""
Acesso ao banco (TimescaleDB / Postgres) via asyncpg.
get_pool() retorna pool compartilhado criado no startup da API.
Se POSTGRES_URL não estiver definido ou falhar, _pool fica None
e salvar_snapshot/buscar_historico viram no-op silencioso.
"""
import json
import os
from typing import Optional, List

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


async def buscar_historico(pool: Optional[asyncpg.Pool], uf: str, cargo: str, ultimas: int = 20) -> List[dict]:
    """Retorna série temporal. Lista vazia se pool=None."""
    if pool is None:
        return []
    try:
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
    except Exception as e:
        print(f"[db] Erro ao buscar histórico: {e}")
        return []
