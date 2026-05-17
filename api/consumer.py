"""
Consome Redis Stream megatron:{uf}:{cargo} e:
1. Faz broadcast via WebSocket para clientes inscritos
2. Persiste snapshot no TimescaleDB
Roda como asyncio task em background.
"""
import json
import os
from typing import Optional, Dict

import redis.asyncio as aioredis

from db import salvar_snapshot
from ws_manager import ConnectionManager

REDIS_URL = os.environ["REDIS_URL"]

# Cache em memória: último snapshot por stream
_last: Dict[str, dict] = {}

# Streams monitorados
UFS    = [u.strip() for u in os.getenv("UFS", "sp").split(",")]
CARGOS = [c.strip() for c in os.getenv("CARGOS", "governador").split(",")]

STREAMS = {
    f"megatron:{uf}:{cargo}": "$"
    for uf in UFS
    for cargo in CARGOS
}


def get_last_snapshot(stream: str) -> Optional[dict]:
    return _last.get(stream)


async def start_consumer(manager: ConnectionManager, pool) -> None:
    """Inicia loop de consumo do Redis Stream."""
    redis = aioredis.from_url(REDIS_URL)
    streams = dict(STREAMS)
    print(f"[consumer] Aguardando streams: {list(streams.keys())}")

    while True:
        try:
            results = await redis.xread(streams, block=2000, count=10)
        except Exception as e:
            print(f"[consumer] Erro xread: {e}")
            continue

        for stream_key_bytes, messages in (results or []):
            stream_key = stream_key_bytes.decode() if isinstance(stream_key_bytes, bytes) else stream_key_bytes

            for _msg_id, fields in messages:
                try:
                    data = json.loads(fields[b"data"] if b"data" in fields else fields["data"])
                    _last[stream_key] = data

                    # broadcast WebSocket
                    _, uf_cargo = stream_key.split(":", 1)  # "megatron:sp:governador" → "sp:governador"
                    room = uf_cargo
                    await manager.broadcast(room, json.dumps(data, ensure_ascii=False))

                    # persist to TimescaleDB
                    parts = stream_key.split(":")  # ["megatron", "sp", "governador"]
                    uf, cargo = parts[1], parts[2]
                    pst_str = data.get("pst", "0%").replace("%", "")
                    pst_pct = float(pst_str)
                    await salvar_snapshot(pool, uf, cargo, pst_pct, data)
                except Exception as e:
                    print(f"[consumer] Erro ao processar {stream_key}: {e}")

                streams[stream_key] = "$"  # avança cursor
