"""
Publica snapshots de dados eleitorais no Redis Stream.
"""
import json
from datetime import datetime, timezone

import redis.asyncio as aioredis


async def publish(redis_client: aioredis.Redis, stream: str, data: dict) -> None:
    """
    Publica payload no Redis Stream com timestamp UTC.
    maxlen=1000 mantém janela deslizante.
    """
    payload = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "data": json.dumps(data, ensure_ascii=False),
    }
    await redis_client.xadd(stream, payload, maxlen=1000)
    print(f"[publisher] → {stream} | pst={data.get('pst', '?')} | hor={data.get('hor', '?')}")
