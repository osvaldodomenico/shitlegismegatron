"""
Entry point do coletor MEGATRON.
APScheduler executa ciclo_coleta a cada INTERVALO segundos.
Após 10 tentativas falhas de conexão Redis, exit(1) para restart pelo Docker.
"""
import asyncio
import os
import sys

import httpx
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fetcher import fetch_if_changed
from publisher import publish
from tse_urls import gerar_tarefas, CARGO_CODIGOS

TSE_BASE_URL = os.environ["TSE_BASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
ELE_1T = os.environ.get("ELE_1T", "001")
INTERVALO = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

_ufs_raw = os.environ.get("UFS", "sp,rj,mg")
_cargos_raw = os.environ.get("CARGOS", "governador")
UFS = [u.strip() for u in _ufs_raw.split(",")]
CARGOS = [c.strip() for c in _cargos_raw.split(",")]

TAREFAS = gerar_tarefas(ele=ELE_1T, ufs=UFS, cargos=CARGOS)


async def ciclo_coleta(redis: aioredis.Redis) -> None:
    """Coleta dados de todas as URLs e publica mudanças no Redis."""
    async with httpx.AsyncClient() as client:
        for tarefa in TAREFAS:
            url = tarefa["url"].replace("{base}", TSE_BASE_URL)
            data = await fetch_if_changed(client, url)
            if data:
                await publish(redis, tarefa["stream"], data)


async def conectar_redis(max_tentativas: int = 10) -> aioredis.Redis:
    """Conecta ao Redis com retry exponencial. Exit(1) após max_tentativas."""
    delay = 1
    for tentativa in range(1, max_tentativas + 1):
        try:
            r = aioredis.from_url(REDIS_URL)
            await r.ping()
            print(f"[collector] Redis conectado após {tentativa} tentativa(s).")
            return r
        except Exception as e:
            print(f"[collector] Redis indisponível (tentativa {tentativa}/{max_tentativas}): {e}")
            if tentativa == max_tentativas:
                print("[collector] Limite de tentativas atingido. Encerrando.")
                sys.exit(1)
            await asyncio.sleep(min(delay, 60))
            delay *= 2


async def main() -> None:
    redis = await conectar_redis()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        ciclo_coleta,
        "interval",
        seconds=INTERVALO,
        args=[redis],
        max_instances=1,
    )
    scheduler.start()
    print(f"[collector] Iniciado. Intervalo: {INTERVALO}s | Tarefas: {len(TAREFAS)}")
    for t in TAREFAS:
        print(f"  → {t['stream']}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
