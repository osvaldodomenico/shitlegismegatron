"""
FastAPI application — API pública do MEGATRON.
Expõe REST e WebSocket. Consumer roda como task asyncio em background.
"""
import asyncio
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db import get_pool, close_pool
from ws_manager import ConnectionManager
from consumer import start_consumer
from routes.health import router as health_router
from routes.resultados import router as resultados_router
from routes.historico import router as historico_router
from routes.selecao import router as selecao_router
import selecao as sel
import db as _db

app = FastAPI(title="MEGATRON API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(resultados_router)
app.include_router(historico_router)
app.include_router(selecao_router)

manager = ConnectionManager()
_consumer_task = None


@app.websocket("/ws/{uf}/{cargo}")
async def websocket_endpoint(
    websocket: WebSocket, uf: str, cargo: str, selecionados: bool = False
):
    """
    `?selecionados=1` inscreve numa room paralela que recebe o payload ja
    recortado nos candidatos acompanhados — ver consumer.start_consumer.
    """
    room = f"{uf}:{cargo}:sel" if selecionados else f"{uf}:{cargo}"
    await manager.connect(websocket, room)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)


@app.on_event("startup")
async def startup():
    global _consumer_task
    pool = await get_pool()
    # Reidrata o cache de selecao: sem isso, um restart da API faria todo mundo
    # perder o filtro ate alguem regravar a escolha.
    for linha in await _db.carregar_todas_selecoes(pool):
        sel.set_cache(linha["uf"], linha["cargo"], linha["sqcands"])
    _consumer_task = asyncio.create_task(start_consumer(manager, pool))
    print("[api] Startup completo.")


@app.on_event("shutdown")
async def shutdown():
    if _consumer_task:
        _consumer_task.cancel()
    await close_pool()
    print("[api] Shutdown completo.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
