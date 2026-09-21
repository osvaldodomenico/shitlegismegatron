"""
/health — verdade operacional unica do MEGATRON.

Antes devolvia so {"status":"ok"}, o que dizia apenas que o processo da API
subiu. Na noite da apuracao a pergunta e outra: **o collector esta coletando?**

O sinal certo e o heartbeat que o collector grava a cada ciclo, e nao a data
dentro do boletim: o fetcher so publica quando o payload MUDA, entao dado
parado pode ser silencio legitimo (fonte estatica, ou nenhuma secao nova
totalizada). Ja heartbeat velho significa collector travado ou morto.
"""
import json
import os
import time

import redis.asyncio as aioredis
from fastapi import APIRouter

import consumer

router = APIRouter()

HEARTBEAT = "megatron:heartbeat:collector"
TOLERANCIA_CICLOS = 3


@router.get("/health")
async def health():
    corridas = len(consumer.STREAMS)
    com_dado = sum(
        1 for s in consumer.STREAMS if consumer.get_last_snapshot(s) is not None
    )

    coletor = {"estado": "desconhecido"}
    try:
        r = aioredis.from_url(os.environ["REDIS_URL"])
        bruto = await r.get(HEARTBEAT)
        await r.aclose()
        if not bruto:
            coletor = {"estado": "sem_heartbeat",
                       "detalhe": "nenhum ciclo concluido ainda"}
        else:
            hb = json.loads(bruto)
            idade = int(time.time()) - int(hb.get("ts", 0))
            limite = int(hb.get("intervalo", 60)) * TOLERANCIA_CICLOS
            coletor = {
                "estado": "ok" if idade <= limite else "parado",
                "idade_segundos": idade,
                "limite_segundos": limite,
                "tarefas": hb.get("tarefas"),
                "publicados_ultimo_ciclo": hb.get("publicados"),
                "falhas_ultimo_ciclo": hb.get("falhas"),
            }
    except Exception as e:
        coletor = {"estado": "erro", "detalhe": str(e)}

    saudavel = coletor.get("estado") == "ok" and (corridas == 0 or com_dado > 0)
    return {
        "status": "ok" if saudavel else "degradado",
        "service": "megatron-api",
        "coletor": coletor,
        "corridas": {"configuradas": corridas, "com_dado": com_dado},
    }
