import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.cidades import router, limpar_cache


def make_app():
    app = FastAPI()
    app.include_router(router)
    return app


LINHAS = [
    {"cod": "71072", "zona": "", "nome": "SÃO PAULO", "pst": 96.6, "validos": 6036690, "hg": "19:30:00",
     "votos": 28493, "pct": "0,47", "atualizado_em": "2026-10-04 22:40:00+00:00"},
    {"cod": "61018", "zona": "", "nome": "ADAMANTINA", "pst": 100.0, "validos": 20000, "hg": "19:30:00",
     "votos": 0, "pct": "0,00", "atualizado_em": "2026-10-04 22:39:00+00:00"},
]


def test_cidades_resume_total_e_lugares_com_voto():
    limpar_cache()
    with patch("db.get_pool", new=AsyncMock(return_value=object())), \
         patch("db.buscar_votos_por_cidade", new=AsyncMock(return_value=LINHAS)):
        r = TestClient(make_app()).get("/candidatos/sp/dep_federal/250002537976/cidades")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total_votos"] == 28493 and corpo["lugares"] == 2 and corpo["com_voto"] == 1
    assert corpo["lista"][0]["nome"] == "SÃO PAULO"
    assert corpo["atualizado_em"].startswith("2026-10-04 22:40")


def test_cidades_404_sem_dado_e_422_nivel_invalido():
    limpar_cache()
    with patch("db.get_pool", new=AsyncMock(return_value=None)), \
         patch("db.buscar_votos_por_cidade", new=AsyncMock(return_value=[])):
        c = TestClient(make_app())
        assert c.get("/candidatos/sp/dep_federal/X/cidades").status_code == 404
        assert c.get("/candidatos/sp/dep_federal/X/cidades?nivel=bairro").status_code == 422
