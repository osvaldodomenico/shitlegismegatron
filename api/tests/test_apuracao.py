import json
import pathlib

import apuracao


def _cand(sq, nm, cc, vap, st="", dvt="Válido"):
    return {"sqcand": sq, "nm": nm, "cc": cc, "vap": str(vap), "st": st, "dvt": dvt}


def _corrida(cands, vagas=2, vv=1000, pst="100,00", ele="546"):
    return {"v": str(vagas), "vv": str(vv), "pst": pst, "ele": ele, "cand": cands}


def test_quociente_despreza_fracao_ate_meio():
    # 1000/3 = 333,33 -> fracao <= 0,5 -> despreza
    assert apuracao.quociente_eleitoral(1000, 3) == 333


def test_quociente_arredonda_acima_de_meio():
    # 1700/3 = 566,67 -> fracao > 0,5 -> soma 1
    assert apuracao.quociente_eleitoral(1700, 3) == 567


def test_quociente_real_de_sp_2022():
    # 23.375.585 votos validos / 70 vagas = 333.936,93 -> 333.937
    assert apuracao.quociente_eleitoral(23375585, 70) == 333937


def test_corrida_majoritaria_nao_tem_quociente():
    assert apuracao.calcular({"vv": "1000", "cand": []}) == {}


def test_barreira_individual_e_10_por_cento_do_qe():
    r = apuracao.calcular(_corrida([_cand("A", "X", "P1", 10)], vagas=2, vv=1000))
    assert r["quociente_eleitoral"] == 500
    assert r["barreira_individual"] == 50
    assert r["por_candidato"]["A"]["passou_barreira"] is False
    assert r["por_candidato"]["A"]["falta_barreira"] == 40


def test_margem_positiva_para_quem_esta_dentro():
    cands = [
        _cand("A", "DENTRO", "P1", 300, st="Eleito por QP"),
        _cand("B", "FORA", "P1", 120),
    ]
    r = apuracao.calcular(_corrida(cands))
    assert r["por_candidato"]["A"]["margem"] == 180
    assert r["por_candidato"]["A"]["referencia"] == "FORA"
    assert r["por_candidato"]["A"]["dentro_do_corte"] is True


def test_margem_negativa_para_quem_esta_fora():
    cands = [
        _cand("A", "DENTRO", "P1", 300, st="Eleito por QP"),
        _cand("B", "FORA", "P1", 120, st="Suplente"),
    ]
    r = apuracao.calcular(_corrida(cands))
    assert r["por_candidato"]["B"]["margem"] == -180
    assert r["por_candidato"]["B"]["referencia"] == "DENTRO"


def test_sem_situacao_publicada_nao_inventa_vagas():
    cands = [_cand("A", "X", "P1", 300), _cand("B", "Y", "P1", 120)]
    r = apuracao.calcular(_corrida(cands))
    assert r["por_candidato"]["A"]["vagas_agremiacao"] is None
    assert r["por_candidato"]["A"]["margem"] is None


def test_votos_anulados_nao_entram_no_ranking():
    cands = [
        _cand("A", "VALIDO", "P1", 100, st="Eleito por QP"),
        _cand("B", "ANULADO", "P1", 900, dvt="Anulado"),
    ]
    r = apuracao.calcular(_corrida(cands))
    assert "B" not in r["por_candidato"]
    assert r["por_candidato"]["A"]["posicao_agremiacao"] == 1


def test_parcial_marcado_enquanto_apuracao_nao_fecha():
    r = apuracao.calcular(_corrida([_cand("A", "X", "P1", 10)], pst="43,20"))
    assert r["parcial"] is True


def test_cada_agremiacao_tem_ranking_proprio():
    cands = [
        _cand("A", "P1-1", "P1", 300, st="Eleito por QP"),
        _cand("B", "P2-1", "P2", 200, st="Eleito por QP"),
        _cand("C", "P2-2", "P2", 100, st="Suplente"),
    ]
    r = apuracao.calcular(_corrida(cands))
    assert r["por_candidato"]["B"]["posicao_agremiacao"] == 1
    assert r["por_candidato"]["C"]["posicao_agremiacao"] == 2
    assert r["por_candidato"]["C"]["margem"] == -100


def test_reproduz_a_apuracao_real_de_sp_2022():
    """
    Regressao contra dado real: se o ranking por agremiacao divergir do `st`
    do TSE, o indicador de corte esta mentindo.
    """
    p = pathlib.Path(__file__).parent / "fixtures" / "sp-dep-federal-2022.json"
    if not p.exists():
        import pytest
        pytest.skip("fixture da apuracao real nao disponivel")
    payload = json.loads(p.read_text())
    r = apuracao.calcular(payload)
    assert r["quociente_eleitoral"] == 333937
    assert r["vagas"] == 70
    # todo eleito precisa estar dentro do corte e com margem >= 0
    eleitos = [v for v in r["por_candidato"].values() if v["dentro_do_corte"]]
    assert len(eleitos) == 70
    assert all(v["margem"] is None or v["margem"] >= 0 for v in eleitos)
    fora = [v for v in r["por_candidato"].values() if not v["dentro_do_corte"]]
    assert all(v["margem"] is None or v["margem"] <= 0 for v in fora)


def test_url_da_foto_segue_o_padrao_do_tse():
    u = apuracao.url_foto("SP", "546", "250001613761")
    assert u.endswith("/546/fotos/sp/250001613761.jpeg")


def test_sem_codigo_de_eleicao_nao_inventa_url_de_foto():
    assert apuracao.url_foto("sp", "", "A1") is None


def test_preparar_calcula_antes_de_filtrar():
    """
    Se os indicadores fossem calculados depois do recorte, o 3o colocado da
    agremiacao viraria "1o de 1".
    """
    cands = [
        _cand("A", "PRIMEIRO", "P1", 300, st="Eleito por QP"),
        _cand("B", "SEGUNDO", "P1", 200, st="Eleito por QP"),
        _cand("C", "TERCEIRO", "P1", 100, st="Suplente"),
    ]
    r = apuracao.preparar(_corrida(cands), "sp", ["C"])
    assert [c["sqcand"] for c in r["cand"]] == ["C"]
    assert r["cand"][0]["ind"]["posicao_agremiacao"] == 3
    assert r["cand"][0]["ind"]["total_agremiacao"] == 3
    assert r["cand"][0]["foto"].endswith("/fotos/sp/C.jpeg")
    assert r["indicadores"]["quociente_eleitoral"] == 500
    assert "por_candidato" not in r["indicadores"]
