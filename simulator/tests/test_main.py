import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_retorna_modo_sim():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "MEGATRON_SIM"


def test_resultado_serve_o_path_real_do_tse():
    resp = client.get("/oficial/ele2026/001/dados-simplificados/sp/sp-c0003-e000001-r.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "pst" in data
    assert "cand" in data
    assert data["cdabr"] == "SP"


def test_resultado_extrai_cargo_do_filename():
    resp = client.get("/oficial/ele2026/001/dados-simplificados/br/br-c0001-e000001-r.json")
    assert resp.status_code == 200
    assert resp.json()["carper"] == "0001"
