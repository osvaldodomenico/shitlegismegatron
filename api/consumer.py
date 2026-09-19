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

# Presidente so existe na abrangencia "br"; os demais cargos so existem por
# UF. Assinar os pares incoerentes criaria streams que nunca recebem dado.
# Mesma regra aplicada em collector/tse_urls.gerar_tarefas.
CARGOS_NACIONAIS = frozenset({"presidente"})

STREAMS = {
    f"megatron:{uf}:{cargo}": "$"
    for uf in UFS
    for cargo in CARGOS
    if (cargo in CARGOS_NACIONAIS) == (uf == "br")
}


def get_last_snapshot(stream: str) -> Optional[dict]:
    return _last.get(stream)


def parse_pst(valor) -> float:
    """
    Converte o campo `pst` do TSE em float.

    O TSE publica percentuais com VIRGULA decimal e sem sinal: "100,00".
    O simulador antigo usava "100.00%" — ambos os formatos sao aceitos aqui
    para nao quebrar em dados legados ja gravados.
    """
    if valor is None:
        return 0.0
    texto = str(valor).replace("%", "").strip()
    if "," in texto:
        # formato TSE: "1.234,56" -> ponto eh milhar, virgula eh decimal
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


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
                    pst_pct = parse_pst(data.get("pst"))
                    await salvar_snapshot(pool, uf, cargo, pst_pct, data)
                except Exception as e:
                    print(f"[consumer] Erro ao processar {stream_key}: {e}")

                streams[stream_key] = "$"  # avança cursor
