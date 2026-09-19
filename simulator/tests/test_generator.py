import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generator import gerar_resultado, _progresso


def test_resultado_tem_campos_do_schema_real_do_tse():
    """Campos que o collector valida: pst, cand, hg (esquema plano)."""
    r = gerar_resultado("sp", "0003")
    assert "pst" in r
    assert "cand" in r
    assert "hg" in r
    assert "cdabr" in r


def test_pst_usa_virgula_decimal_sem_percent():
    """O TSE publica '100,00', nunca '100.00%'."""
    r = gerar_resultado("sp", "0003")
    assert "%" not in r["pst"]
    assert "," in r["pst"]
    pct = float(r["pst"].replace(",", "."))
    assert 0.0 <= pct <= 100.0


def test_candidatos_sao_lista_plana_no_topo():
    r = gerar_resultado("sp", "0003")
    assert isinstance(r["cand"], list)
    assert len(r["cand"]) > 0
    for c in r["cand"]:
        assert "vap" in c
        assert "pvap" in c
        assert "," in c["pvap"]


def test_campo_e_e_total_de_eleitores_string():
    """No TSE real, `e` no topo eh o eleitorado apto (string), nao uma lista."""
    r = gerar_resultado("sp", "0003")
    assert isinstance(r["e"], str)
    assert r["e"].isdigit()


def test_progresso_entre_0_e_1():
    p = _progresso()
    assert 0.0 <= p <= 1.0


def test_abrangencia_refletida_no_resultado():
    r = gerar_resultado("rj", "0003")
    assert r["cdabr"] == "RJ"
    assert r["tpabr"] == "uf"
    nacional = gerar_resultado("br", "0001")
    assert nacional["cdabr"] == "br"
    assert nacional["tpabr"] == "br"
