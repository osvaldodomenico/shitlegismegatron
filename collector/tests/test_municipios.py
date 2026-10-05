import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from municipios import (url_config, url_municipio, url_abrangencia, url_da, municipios_da_uf,
                        ufs_do_config, enxugar, _int, _num, tarefas_de)

BASE = "https://resultados.tse.jus.br/oficial/ele2026"


def test_urls_seguem_o_esquema_do_tse():
    assert url_config(BASE, "6259") == f"{BASE}/6259/config/mun-e006259-cm.json"
    assert url_municipio(BASE, "6259", "sp", "71072", "dep_federal") == \
        f"{BASE}/6259/dados/sp/sp71072-c0006-e006259-u.json"
    assert url_municipio(BASE, "6259", "sp", "71072", "dep_federal", "20") == \
        f"{BASE}/6259/dados/sp/sp71072-z0020-c0006-e006259-u.json"
    # presidente usa o codigo nacional, mesmo no arquivo da cidade
    assert url_municipio(BASE, "6257", "sp", "71072", "presidente") == \
        f"{BASE}/6257/dados/sp/sp71072-c0001-e006257-u.json"
    assert url_abrangencia(BASE, "6257", "rj", "presidente") == f"{BASE}/6257/dados/rj/rj-c0001-e006257-u.json"
    assert url_abrangencia(BASE, "6257", "br", "presidente") == f"{BASE}/6257/dados/br/br-c0001-e006257-u.json"


def test_municipios_da_uf_filtra_e_normaliza():
    cm = {"abr": [
        {"cd": "RJ", "mu": [{"cd": "1", "cdi": "33", "nm": "RIO", "c": "s", "z": ["1"]}]},
        {"cd": "SP", "mu": [{"cd": "71072", "cdi": "3550308", "nm": "SÃO PAULO", "c": "s", "z": ["0020", "248"]},
                            {"cd": "61018", "cdi": "3500105", "nm": "ADAMANTINA", "c": "n", "z": ["0157"]}]},
        {"cd": "ZZ", "mu": []},
    ]}
    sp = municipios_da_uf(cm, "sp")
    assert [m["cod"] for m in sp] == ["71072", "61018"]
    assert sp[0] == {"cod": "71072", "ibge": "3550308", "nome": "SÃO PAULO", "capital": True, "zonas": ["0020", "0248"]}
    assert municipios_da_uf(cm, "mg") == []
    assert ufs_do_config(cm) == ["rj", "sp"]       # zz (exterior) fica de fora


def test_tarefas_cobrem_todos_os_niveis():
    muns = [{"cod": "71072", "nome": "SÃO PAULO", "zonas": ["0020", "0248"]}, {"cod": "61018", "nome": "ADAMANTINA", "zonas": ["0157"]}]
    t = tarefas_de(muns, ["presidente", "governador"], ["municipio", "zona", "uf", "br"],
                   uf="sp", ufs=["rj", "sp"], ele="6259", ele_br="6257")
    por_nivel = {}
    for x in t:
        por_nivel.setdefault(x["nivel"], []).append(x)
    assert len(por_nivel["municipio"]) == 2 * 2 and len(por_nivel["zona"]) == 2 * 3
    # uf: presidente em todas as UFs (2) + governador so na propria (1)
    assert sorted((x["uf"], x["cargo"]) for x in por_nivel["uf"]) == [("rj", "presidente"), ("sp", "governador"), ("sp", "presidente")]
    assert por_nivel["br"] == [{"nivel": "br", "uf": "br", "cod": "br", "zona": "", "cargo": "presidente", "nome": "BRASIL", "ele": "6257"}]
    # presidente carrega o codigo nacional; governador, o da UF
    assert {x["ele"] for x in t if x["cargo"] == "presidente"} == {"6257"}
    assert {x["ele"] for x in t if x["cargo"] == "governador"} == {"6259"}
    assert url_da(BASE, por_nivel["br"][0]).endswith("/6257/dados/br/br-c0001-e006257-u.json")
    assert url_da(BASE, por_nivel["zona"][0]).endswith("/6257/dados/sp/sp71072-z0020-c0001-e006257-u.json")


def test_enxugar_guarda_totais_e_federacoes_alem_dos_candidatos():
    flat = {"ele": "6259", "cdabr": "71072", "dg": "04/10/2026", "hg": "19:00:00", "tf": "n",
            "pst": "50,00", "e": "100", "v": "70", "tv": "90", "vv": "80", "vnom": "70",
            "partidos": [{"sg": "REPUBLICANOS", "tvan": "10"}], "vagas_por_agremiacao": {"a": 1},
            "cand": [{"sqcand": "1", "n": "1055", "nm": "MILTON", "nmu": "MILTON VIEIRA", "cc": "REPUBLICANOS",
                      "vap": "5", "pvap": "6,25", "st": "", "dt": "01/01/1970", "vs": [{"x": 1}], "seq": "9"}]}
    bruto = {"s": {"ts": "9", "st": "4", "pst": "50,00"}, "e": {"te": "100", "c": "90", "a": "10", "pa": "10,00"},
             "v": {"tv": "90", "vv": "80", "vb": "5", "tvn": "5"},
             "carg": [{"fed": [{"n": "101", "sg": "PT/PC do B/PV"}]}]}
    enx = enxugar(flat, bruto)
    assert enx["cand"] == [{"sqcand": "1", "n": "1055", "nm": "MILTON", "nmu": "MILTON VIEIRA",
                            "cc": "REPUBLICANOS", "vap": "5", "pvap": "6,25", "st": ""}]
    assert enx["totais"]["e"]["c"] == "90" and enx["totais"]["v"]["vb"] == "5" and enx["totais"]["s"]["st"] == "4"
    assert enx["federacoes"] == [{"n": "101", "sg": "PT/PC do B/PV"}]
    assert "seq" not in str(enx) and "vs" not in enx["cand"][0]
    # sem o bruto (compatibilidade), totais ficam vazios mas presentes
    assert enxugar(flat)["totais"] == {"s": {}, "e": {}, "v": {}}


def test_conversoes_numericas_do_tse():
    assert _int("1.234") == 1234 and _int("") == 0 and _int(None) == 0
    assert _num("51,51") == 51.51 and _num("1.234,5") == 1234.5
