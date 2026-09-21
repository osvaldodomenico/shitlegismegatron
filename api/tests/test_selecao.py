import pytest

import selecao


@pytest.fixture(autouse=True)
def _limpa():
    selecao.limpar_cache()
    yield
    selecao.limpar_cache()


def _payload():
    return {
        "pst": "42,00",
        "vv": "1000",
        "cand": [
            {"sqcand": "A1", "seq": "3", "nm": "BOULOS", "cc": "PSOL", "n": "5050", "vap": "10"},
            {"sqcand": "B2", "seq": "1", "nm": "ZAMBELLI", "cc": "PL", "n": "2222", "vap": "20"},
            {"sqcand": "C3", "seq": "2", "nm": "SALLES", "cc": "PL", "n": "1717", "vap": "30"},
        ],
    }


def test_selecao_vazia_devolve_payload_intacto():
    p = _payload()
    assert selecao.filtrar(p, []) is p


def test_filtra_por_sqcand_e_respeita_a_ordem_escolhida():
    out = selecao.filtrar(_payload(), ["C3", "A1"])
    assert [c["sqcand"] for c in out["cand"]] == ["C3", "A1"]


def test_filtrar_preserva_totais_da_corrida():
    out = selecao.filtrar(_payload(), ["A1"])
    assert out["pst"] == "42,00" and out["vv"] == "1000"


def test_filtrar_nao_muta_o_payload_original():
    p = _payload()
    selecao.filtrar(p, ["A1"])
    assert len(p["cand"]) == 3


def test_sqcand_inexistente_e_simplesmente_ignorado():
    out = selecao.filtrar(_payload(), ["A1", "NAO_EXISTE"])
    assert [c["sqcand"] for c in out["cand"]] == ["A1"]


def test_normalizar_remove_duplicata_preservando_ordem():
    assert selecao.normalizar(["B2", "A1", "B2"]) == ["B2", "A1"]


def test_normalizar_recusa_mais_que_o_limite():
    with pytest.raises(ValueError):
        selecao.normalizar([f"X{i}" for i in range(selecao.MAX_SELECIONADOS + 1)])


def test_normalizar_aceita_exatamente_o_limite():
    entrada = [f"X{i}" for i in range(selecao.MAX_SELECIONADOS)]
    assert selecao.normalizar(entrada) == entrada


def test_cache_guarda_e_devolve_por_corrida():
    selecao.set_cache("sp", "dep_federal", ["A1", "B2"])
    assert selecao.get("sp", "dep_federal") == ["A1", "B2"]
    assert selecao.get("rj", "dep_federal") == []


def test_resumir_candidatos_descarta_campos_pesados():
    r = selecao.resumir_candidatos(_payload())
    assert len(r) == 3
    assert set(r[0]) == {"sqcand", "nm", "cc", "n"}
