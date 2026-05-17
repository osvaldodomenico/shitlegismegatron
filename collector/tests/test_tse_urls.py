import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tse_urls import url_resultado, url_fixos, gerar_tarefas

def test_url_resultado_formato():
    url = url_resultado(base="https://tse.example.com/ele2026", ele="544", uf="sp", cargo="0003")
    assert url == "https://tse.example.com/ele2026/544/dados-simplificados/sp/sp-c0003-e000544-r.json"

def test_url_resultado_ele_com_zero_padding():
    url = url_resultado(base="https://tse.example.com/ele2026", ele="1", uf="rj", cargo="0001")
    assert "-e000001-" in url

def test_url_fixos_formato():
    url = url_fixos(base="https://tse.example.com/ele2026", ele="544", cargo="0003")
    assert url == "https://tse.example.com/ele2026/544/config/ele-c0003-e000544-cf.json"

def test_gerar_tarefas_produto_cartesiano():
    tarefas = gerar_tarefas(ele="544", ufs=["sp", "rj"], cargos=["governador", "presidente"])
    assert len(tarefas) == 2  # 2 UFs × 1 cargo each = 2 tarefas de resultado
    streams = [t["stream"] for t in tarefas]
    assert "megatron:sp:governador" in streams
    assert "megatron:rj:presidente" in streams
