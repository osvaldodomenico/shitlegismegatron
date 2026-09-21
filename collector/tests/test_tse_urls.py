import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tse_urls import url_resultado, gerar_tarefas

BASE = "https://resultados.tse.jus.br/oficial/ele2026"


def test_url_resultado_formato():
    """Esquema real da CDN: dados-simplificados/<abr>/<abr>-c<CCCC>-e<ELEICA>-r.json"""
    url = url_resultado(base=BASE, ele="546", uf="sp", cargo="0006")
    assert url == f"{BASE}/546/dados-simplificados/sp/sp-c0006-e000546-r.json"


def test_url_resultado_presidente_br():
    """Presidente eh publicado na abrangencia nacional 'br'."""
    url = url_resultado(base=BASE, ele="544", uf="br", cargo="0001")
    assert url == f"{BASE}/544/dados-simplificados/br/br-c0001-e000544-r.json"


def test_url_resultado_ele_com_zero_padding():
    """ELEICA com 1 digito deve virar 6 no nome do arquivo (nao no path)."""
    url = url_resultado(base=BASE, ele="1", uf="rj", cargo="0003")
    assert "/1/dados-simplificados/rj/" in url
    assert "-e000001-r.json" in url


def test_gerar_tarefas_descarta_pares_inexistentes():
    """
    presidente so existe em 'br'; governador so existe por UF.
    2 UFs + br x 2 cargos = 3 tarefas validas (nao 6).
    """
    tarefas = gerar_tarefas(ele="546", ufs=["sp", "rj", "br"], cargos=["governador", "presidente"])
    pares = {(t["uf"], t["cargo"]) for t in tarefas}
    assert pares == {("sp", "governador"), ("rj", "governador"), ("br", "presidente")}


def test_gerar_tarefas_usa_codigo_nacional_para_presidente():
    """Presidente usa ELE nacional; cargos de UF usam o ELE por UF."""
    tarefas = gerar_tarefas(
        ele="546", ufs=["sp", "br"], cargos=["governador", "presidente"], ele_nacional="544"
    )
    por_cargo = {t["cargo"]: t["url"] for t in tarefas}
    assert "/546/dados-simplificados/sp/sp-c0003-e000546-r.json" in por_cargo["governador"]
    assert "/544/dados-simplificados/br/br-c0001-e000544-r.json" in por_cargo["presidente"]


def test_gerar_tarefas_ele_nacional_default():
    """Sem ele_nacional, presidente cai no mesmo codigo."""
    tarefas = gerar_tarefas(ele="544", ufs=["br"], cargos=["presidente"])
    assert "-e000544-r.json" in tarefas[0]["url"]


def test_gerar_tarefas_produto_cartesiano_por_uf():
    """3 UFs x 2 cargos de UF = 6 tarefas (nao 3, como seria com zip)."""
    tarefas = gerar_tarefas(ele="546", ufs=["sp", "rj", "mg"], cargos=["governador", "senador"])
    assert len(tarefas) == 6


def test_gerar_tarefas_deputado_federal():
    """Cenario alvo do MEGATRON: dep_federal para 11 UFs."""
    ufs = ["sp", "rj", "mg", "ba", "rs", "pr", "pe", "ce", "pa", "ma", "go"]
    tarefas = gerar_tarefas(ele="546", ufs=ufs, cargos=["dep_federal"])
    assert len(tarefas) == 11
    for t in tarefas:
        assert "c0006" in t["url"]  # dep_federal sempre codigo 0006
        assert t["url"].endswith("-r.json")
        assert t["stream"].startswith("megatron:")
        assert t["stream"].endswith(":dep_federal")


def test_gerar_tarefas_lista_vazia():
    assert gerar_tarefas(ele="546", ufs=[], cargos=["governador"]) == []
    assert gerar_tarefas(ele="546", ufs=["sp"], cargos=[]) == []


def test_caminho_e_sufixo_vem_de_env(monkeypatch):
    """
    Se o TSE mudar o caminho em 04/10, a saida tem que ser trocavel pelo .env,
    sem rebuild. Recarrega o modulo porque a leitura do env e no import.
    """
    import importlib
    import tse_urls

    monkeypatch.setenv("TSE_PATH_DADOS", "dados")
    monkeypatch.setenv("TSE_SUFIXO", "u")
    importlib.reload(tse_urls)
    try:
        u = tse_urls.url_resultado("BASE", "546", "sp", "0006")
        assert u == "BASE/546/dados/sp/sp-c0006-e000546-u.json"
    finally:
        monkeypatch.delenv("TSE_PATH_DADOS")
        monkeypatch.delenv("TSE_SUFIXO")
        importlib.reload(tse_urls)


def test_padrao_continua_dados_simplificados():
    import tse_urls
    u = tse_urls.url_resultado("BASE", "546", "sp", "0006")
    assert u == "BASE/546/dados-simplificados/sp/sp-c0006-e000546-r.json"
