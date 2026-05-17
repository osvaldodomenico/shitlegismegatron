from fastapi import APIRouter

import db

router = APIRouter()

@router.get("/historico/{uf}/{cargo}")
async def get_historico(uf: str, cargo: str, ultimas: int = 20):
    pool = await db.get_pool()
    rows = await db.buscar_historico(pool, uf, cargo, ultimas)
    return rows
