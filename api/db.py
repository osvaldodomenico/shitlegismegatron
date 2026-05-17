"""
Acesso ao TimescaleDB via asyncpg.
get_pool() retorna pool compartilhado criado no startup da API.
"""
import json
import os
from typing import Optional, List

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
    await pool.execute(
        """
        INSERT INTO snapshots (uf, cargo, pst_pct, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        uf, cargo, pst_pct, json.dumps(payload, ensure_ascii=False),
    )


async def buscar_historico(pool: asyncpg.Pool, uf: str, cargo: str, ultimas: int = 20) -> List[dict]:
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
