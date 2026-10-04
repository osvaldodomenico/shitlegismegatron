import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import db


@pytest.mark.asyncio
async def test_historico_so_devolve_snapshots_de_hoje(mock_pool):
    """
    A tabela snapshots guarda os ensaios (dados de 2022 a 100%). Em 04/10 o
    grafico de evolucao comecava em 100% e caia a 0% por causa deles. O corte
    e por dia de Brasilia, no SQL, para nao depender de limpar o banco.
    """
    await db.buscar_historico(mock_pool, "sp", "dep_federal", 30)

    sql, uf, cargo, ultimas, desde = mock_pool.fetch.call_args.args
    assert "time >= $4" in sql
    assert (uf, cargo, ultimas) == ("sp", "dep_federal", 30)

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    assert desde.tzinfo is not None
    assert (desde.year, desde.month, desde.day) == (hoje.year, hoje.month, hoje.day)
    assert (desde.hour, desde.minute, desde.second) == (0, 0, 0)


@pytest.mark.asyncio
async def test_historico_sem_pool_devolve_lista_vazia():
    assert await db.buscar_historico(None, "sp", "dep_federal") == []
