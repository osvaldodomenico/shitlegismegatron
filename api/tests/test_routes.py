import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from routes.health import router as health_router
from routes.resultados import router as resultados_router

def make_app():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(health_router)
    app.include_router(resultados_router)
    return app

def test_health_sempre_responde_200_e_identifica_o_servico():
    """
    /health responde 200 mesmo degradado: quem monitora precisa LER o motivo,
    nao levar timeout. O veredito esta no corpo, nao no status HTTP.
    """
    client = TestClient(make_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["service"] == "megatron-api"
    assert corpo["status"] in ("ok", "degradado")


def test_health_denuncia_collector_sem_redis():
    """
    Sem Redis alcancavel nao da para saber se o collector esta vivo — isso e
    'degradado', nunca 'ok'. Em 04/10 um 'ok' mentiroso aqui custaria a noite.
    """
    client = TestClient(make_app())
    corpo = client.get("/health").json()
    assert "coletor" in corpo and "corridas" in corpo
    if corpo["coletor"]["estado"] != "ok":
        assert corpo["status"] == "degradado"

def test_resultado_404_quando_sem_dados():
    with patch("consumer.get_last_snapshot", return_value=None):
        client = TestClient(make_app())
        resp = client.get("/resultados/sp/governador")
    assert resp.status_code == 404

def test_resultado_retorna_snapshot():
    snapshot = {"pst": "50%", "hor": "22:00:00"}
    with patch("consumer.get_last_snapshot", return_value=snapshot):
        client = TestClient(make_app())
        resp = client.get("/resultados/sp/governador")
    assert resp.status_code == 200
    assert resp.json()["pst"] == "50%"
