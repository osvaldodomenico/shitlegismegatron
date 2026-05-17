import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_retorna_modo_sim():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "MEGATRON_SIM"

def test_resultado_variavel_retorna_campos_obrigatorios():
    resp = client.get("/oficial/ele2026/001/dados-simplificados/sp/sp-c0003-e000001-r.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "pst" in data
    assert "e" in data
    assert data["cdabr"] == "sp"

def test_resultado_variavel_extrai_cargo_do_filename():
    resp = client.get("/oficial/ele2026/001/dados-simplificados/rj/rj-c0001-e000001-r.json")
    assert resp.status_code == 200
    assert resp.json()["cdabr"] == "rj"
