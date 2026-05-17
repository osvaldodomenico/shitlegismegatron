from fastapi import APIRouter, HTTPException

import consumer

router = APIRouter()

@router.get("/resultados/{uf}/{cargo}")
async def get_resultado(uf: str, cargo: str):
    stream = f"megatron:{uf}:{cargo}"
    snap = consumer.get_last_snapshot(stream)
    if snap is None:
        raise HTTPException(status_code=404, detail="Sem dados ainda")
    return snap
