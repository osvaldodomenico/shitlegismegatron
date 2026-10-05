import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tse_nested import achatar


def _payload():
    return {
        "ele": "6259", "tpabr": "uf", "cdabr": "sp",
        "s": {"pst": "10,00"}, "e": {"e": "100"}, "v": {"vv": "1000", "vnom": "900", "tv": "1100"},
        "carg": [{
            "cd": "6", "nv": "70",
            "agr": [
                {"n": "A1", "nm": "REPUBLICANOS", "vag": "6", "par": [
                    {"n": "10", "sg": "REPUBLICANOS", "nm": "REPUBLICANOS", "tvtn": "800", "tvtl": "13", "tvan": "813",
                     "cand": [{"sqcand": "1", "n": "1055", "nm": "MILTON", "vap": "500", "st": ""}]},
                ]},
                {"n": "A2", "nm": "FED PT", "vag": "2", "par": [
                    {"n": "13", "sg": "PT", "nm": "PT", "tvtn": "100", "tvtl": "5", "tvan": "105", "cand": []},
                ]},
            ],
        }],
    }


def test_achatar_publica_totais_por_partido():
    """Votos nominais + legenda e vagas da agremiacao — o que decide as cadeiras."""
    flat = achatar(_payload())
    rep = next(p for p in flat["partidos"] if p["sg"] == "REPUBLICANOS")
    assert rep == {"n": "10", "sg": "REPUBLICANOS", "nm": "REPUBLICANOS", "agr": "A1",
                   "vag": "6", "tvtn": "800", "tvtl": "13", "tvan": "813"}
    assert [p["sg"] for p in flat["partidos"]] == ["REPUBLICANOS", "PT"]
    # o resto do contrato plano continua igual
    assert flat["pst"] == "10,00" and flat["cand"][0]["cc"] == "REPUBLICANOS"


def test_achatar_publica_vagas_em_v_e_total_de_votos_em_tv():
    flat = achatar(_payload())
    assert flat["v"] == "70"       # carg.nv — vagas da corrida (quociente = vv / v)
    assert flat["tv"] == "1100"    # total de votos apurados


def test_eleito_com_e_s_nao_vira_anulado_quando_o_tse_manda_dvt():
    """05/10/2026: `e` = eleito; `dvt` vem pronto. Eleito NAO pode virar anulado."""
    p = _payload()
    c = p["carg"][0]["agr"][0]["par"][0]["cand"][0]
    c.update({"e": "s", "st": "Eleito", "dvt": "Válido"})
    assert achatar(p)["cand"][0]["dvt"] == "Válido"
    c["dvt"] = "Anulado"
    assert achatar(p)["cand"][0]["dvt"] == "Anulado"
