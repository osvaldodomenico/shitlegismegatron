import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from municipios import url_config, url_municipio, municipios_da_uf, enxugar, _int, _num, tarefas_de


def test_urls_seguem_o_esquema_municipal_do_tse():
    base = "https://resultados.tse.jus.br/oficial/ele2026"
    assert url_config(base, "6259") == f"{base}/6259/config/mun-e006259-cm.json"
    assert url_municipio(base, "6259", "sp", "71072", "dep_federal") == \
        f"{base}/6259/dados/sp/sp71072-c0006-e006259-u.json"
    assert url_municipio(base, "6259", "sp", "71072", "governador").endswith("sp71072-c0003-e006259-u.json")
    # zona dentro da cidade: "-z0020" colado no codigo do municipio
    assert url_municipio(base, "6259", "sp", "71072", "dep_federal", "20") == \
        f"{base}/6259/dados/sp/sp71072-z0020-c0006-e006259-u.json"


def test_municipios_da_uf_filtra_e_normaliza():
    cm = {"abr": [
        {"cd": "RJ", "mu": [{"cd": "1", "cdi": "33", "nm": "RIO", "c": "s"}]},
        {"cd": "SP", "mu": [{"cd": "71072", "cdi": "3550308", "nm": "SÃO PAULO", "c": "s", "z": ["0020", "248"]},
                            {"cd": "61018", "cdi": "3500105", "nm": "ADAMANTINA", "c": "n", "z": ["0157"]}]},
    ]}
    sp = municipios_da_uf(cm, "sp")
    assert [m["cod"] for m in sp] == ["71072", "61018"]
    assert sp[0] == {"cod": "71072", "ibge": "3550308", "nome": "SÃO PAULO", "capital": True, "zonas": ["0020", "0248"]}
    assert municipios_da_uf(cm, "mg") == []


def test_enxugar_mantem_so_o_que_a_analise_usa():
    flat = {"ele": "6259", "cdabr": "71072", "dg": "04/10/2026", "hg": "19:00:00", "tf": "n",
            "pst": "50,00", "e": "100", "v": "90", "vv": "80", "vnom": "70",
            "partidos": [{"sg": "REPUBLICANOS", "tvan": "10"}], "vagas_por_agremiacao": {"a": 1},
            "cand": [{"sqcand": "1", "n": "1055", "nm": "MILTON", "nmu": "MILTON VIEIRA", "cc": "REPUBLICANOS",
                      "vap": "5", "pvap": "6,25", "st": "", "dt": "01/01/1970", "vs": [{"x": 1}], "seq": "9"}]}
    enx = enxugar(flat)
    assert enx["cand"] == [{"sqcand": "1", "n": "1055", "nm": "MILTON", "nmu": "MILTON VIEIRA",
                            "cc": "REPUBLICANOS", "vap": "5", "pvap": "6,25", "st": ""}]
    assert enx["partidos"] == [{"sg": "REPUBLICANOS", "tvan": "10"}]
    assert "seq" not in json_dumps(enx) and "vs" not in enx["cand"][0]


def json_dumps(o):
    import json
    return json.dumps(o)


def test_conversoes_numericas_do_tse():
    assert _int("1.234") == 1234 and _int("") == 0 and _int(None) == 0
    assert _num("51,51") == 51.51 and _num("1.234,5") == 1234.5


def test_tarefas_cobrem_municipio_e_cada_zona_dele():
    muns = [{"cod": "71072", "zonas": ["0020", "0248"]}, {"cod": "61018", "zonas": ["0157"]}]
    t = tarefas_de(muns, ["dep_federal", "governador"], ["municipio", "zona"])
    assert len(t) == 2 * (2 + 3)      # 2 cargos x (2 municipios + 3 zonas)
    assert (muns[0], "dep_federal", "") in t and (muns[0], "dep_federal", "0248") in t
    assert len(tarefas_de(muns, ["dep_federal"], ["municipio"])) == 2
    assert len(tarefas_de(muns, ["dep_federal"], ["zona"])) == 3
