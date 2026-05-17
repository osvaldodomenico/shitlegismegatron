import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from generator import gerar_resultado, _progresso

def test_resultado_tem_campos_obrigatorios():
    r = gerar_resultado("sp", "governador")
    assert "pst" in r
    assert "e" in r
    assert "hor" in r
    assert "cdabr" in r

def test_pst_e_percentual_valido():
    r = gerar_resultado("sp", "governador")
    pct = float(r["pst"].replace("%", ""))
    assert 0.0 <= pct <= 100.0

def test_candidatos_tem_votos():
    r = gerar_resultado("sp", "governador")
    for mun in r["e"]:
        for c in mun["c"]:
            assert "vap" in c
            assert "pvap" in c

def test_progresso_entre_0_e_1():
    p = _progresso()
    assert 0.0 <= p <= 1.0

def test_uf_refletida_no_resultado():
    r = gerar_resultado("rj", "governador")
    assert r["cdabr"] == "rj"
    assert r["e"][0]["cd"] == "rj"
