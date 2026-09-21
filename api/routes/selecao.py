"""
Rotas da selecao compartilhada de candidatos (maximo 5 por corrida).

/candidatos  -> lista enxuta para montar o seletor (1429 nomes sem os campos
                pesados: ~70 KB em vez de ~240 KB)
/selecao     -> le e grava quem esta sendo acompanhado
"""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import consumer
import db
import selecao as sel

router = APIRouter()


class SelecaoIn(BaseModel):
    sqcands: List[str]


def _snapshot(uf: str, cargo: str) -> dict:
    snap = consumer.get_last_snapshot(f"megatron:{uf}:{cargo}")
    if snap is None:
        raise HTTPException(status_code=404, detail="Sem dados ainda")
    return snap


@router.get("/candidatos/{uf}/{cargo}")
async def get_candidatos(uf: str, cargo: str):
    """Lista enxuta para o seletor, ordenada por nome."""
    resumo = sel.resumir_candidatos(_snapshot(uf, cargo))
    resumo.sort(key=lambda c: (c.get("nm") or ""))
    return {"uf": uf, "cargo": cargo, "total": len(resumo), "candidatos": resumo}


@router.get("/selecao/{uf}/{cargo}")
async def get_selecao(uf: str, cargo: str):
    return {
        "uf": uf,
        "cargo": cargo,
        "sqcands": sel.get(uf, cargo),
        "maximo": sel.MAX_SELECIONADOS,
    }


@router.put("/selecao/{uf}/{cargo}")
async def put_selecao(uf: str, cargo: str, corpo: SelecaoIn):
    """
    Grava a selecao. Cache em memoria e atualizado mesmo se o Postgres estiver
    fora: o filtro continua valendo na sessao, e `persistido` avisa que a
    escolha nao sobrevive a um restart.
    """
    try:
        sqcands = sel.normalizar(corpo.sqcands)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    pool = await db.get_pool()
    persistido = await db.salvar_selecao(pool, uf, cargo, sqcands)
    sel.set_cache(uf, cargo, sqcands)
    return {
        "uf": uf,
        "cargo": cargo,
        "sqcands": sqcands,
        "persistido": persistido,
    }
