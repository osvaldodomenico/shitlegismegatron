"""
Votacao de UM candidato por cidade (ou por zona), lida da tabela
`votos_municipio` que o collector_municipios grava a cada 5 min.

Fica sob /candidatos/... de proposito: esse prefixo ja esta na regra do
Traefik; um prefixo novo exigiria recriar o container da API no meio da
apuracao so para o proxy reler a label.
"""
import time
from typing import Dict, Tuple

from fastapi import APIRouter, HTTPException

import db

router = APIRouter()

NIVEIS = ("municipio", "zona")
_TTL = 60  # s — a consulta explode o jsonb de 645 cidades (~0,5 s); cache curto basta
_cache: Dict[Tuple[str, str, str, str], Tuple[float, dict]] = {}


@router.get("/candidatos/{uf}/{cargo}/{sqcand}/cidades")
async def get_cidades(uf: str, cargo: str, sqcand: str, nivel: str = "municipio"):
    if nivel not in NIVEIS:
        raise HTTPException(status_code=422, detail=f"nivel deve ser um de {NIVEIS}")
    chave = (uf, cargo, sqcand, nivel)
    agora = time.monotonic()
    guardado = _cache.get(chave)
    if guardado and agora - guardado[0] < _TTL:
        return guardado[1]

    pool = await db.get_pool()
    linhas = await db.buscar_votos_por_cidade(pool, uf, cargo, sqcand, nivel)
    if not linhas:
        raise HTTPException(status_code=404, detail="Sem votacao por cidade para este candidato ainda")

    total = sum(l["votos"] for l in linhas)
    com_voto = sum(1 for l in linhas if l["votos"] > 0)
    resposta = {
        "uf": uf, "cargo": cargo, "sqcand": sqcand, "nivel": nivel,
        "total_votos": total,
        "lugares": len(linhas),
        "com_voto": com_voto,
        "atualizado_em": max((l["atualizado_em"] for l in linhas), default=None),
        "lista": linhas,
    }
    _cache[chave] = (agora, resposta)
    return resposta


def limpar_cache() -> None:
    _cache.clear()
