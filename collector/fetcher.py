"""
Fetch com diff-hash: só retorna dados se houve mudança desde a última coleta.
Evita publicações e writes desnecessários no Redis.
Valida schema mínimo do TSE; loga alerta se estrutura mudou.
"""
import hashlib
import json
import sys
from typing import Optional

import httpx

HEADERS = {
    "User-Agent": "Megatron/1.0 (Election Monitor)",
    "Accept": "application/json",
    "Referer": "https://resultados.tse.jus.br/",
}

# Campos obrigatórios no payload TSE
REQUIRED_KEYS = frozenset({"pst", "e", "hor"})

# Cache em memória: url → MD5 hash do último payload
_snapshots: dict[str, str] = {}


def _hash(data: dict) -> str:
    return hashlib.md5(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


async def fetch_if_changed(client: httpx.AsyncClient, url: str) -> Optional[dict]:
    """
    Faz GET na URL. Retorna o payload se houve mudança desde a última chamada.
    Retorna None se os dados são idênticos, schema inválido, ou se houve erro.
    """
    try:
        r = await client.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Schema validator: alerta se campos obrigatórios estão ausentes
        if not REQUIRED_KEYS.issubset(data.keys()):
            print(
                f"[fetcher] WARNING schema inesperado em {url}: "
                f"keys={list(data.keys())}",
                file=sys.stderr,
            )
            return None
        h = _hash(data)
        if _snapshots.get(url) == h:
            return None
        _snapshots[url] = h
        return data
    except Exception as exc:
        print(f"[fetcher] ERRO ao buscar {url}: {exc}")
        return None
