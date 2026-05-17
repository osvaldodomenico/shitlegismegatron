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

def test_health_retorna_ok():
    client = TestClient(make_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "megatron-api"

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
