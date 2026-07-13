import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tse_urls import (
    url_resultado,
    url_eleitos,
    url_acompanhamento_uf,
    url_config_eleicoes,
    url_fixos,
    gerar_tarefas,
)


def test_url_resultado_formato():
    """Esquema oficial TSE 2024+: dados/<uf>/<uf>-c<CCCC>-e<ELEICA>-u.json"""
    url = url_resultado(base="https://resultados.tse.jus.br/oficial/ele2026", ele="544", uf="sp", cargo="0006")
    assert url == "https://resultados.tse.jus.br/oficial/ele2026/544/dados/sp/sp-c0006-e000544-u.json"


def test_url_resultado_deputado_federal_sp():
    """Caso de uso principal do MEGATRON: dep_federal SP."""
    url = url_resultado(base="https://resultados.tse.jus.br/oficial/ele2026", ele="544", uf="sp", cargo="0006")
    assert "/dados/sp/" in url
    assert url.endswith("-u.json")
    assert "c0006" in url  # dep_federal


def test_url_resultado_presidente_br():
    """Presidente é agregado por BR (cdabr='br'), nao por UF."""
    url = url_resultado(base="https://resultados.tse.jus.br/oficial/ele2026", ele="544", uf="br", cargo="0001")
    assert url == "https://resultados.tse.jus.br/oficial/ele2026/544/dados/br/br-c0001-e000544-u.json"


def test_url_resultado_ele_com_zero_padding():
    """ELEICA com 1 digito deve virar 6 (zero padding)."""
    url = url_resultado(base="https://resultados.tse.jus.br/oficial/ele2026", ele="1", uf="rj", cargo="0001")
    assert "-e000001-" in url
    assert url.endswith("-u.json")


def test_url_eleitos_formato():
    """EA10 — arquivo de eleitos por UF/cargo (sufixo -e)."""
    url = url_eleitos(base="https://resultados.tse.jus.br/oficial/ele2026", ele="544", uf="sp", cargo="0003")
    assert url == "https://resultados.tse.jus.br/oficial/ele2026/544/dados/sp/sp-c0003-e000544-e.json"
    assert url.endswith("-e.json")


def test_url_acompanhamento_uf_formato():
    """EA15 — acompanhamento UF (sufixo -ab)."""
    url = url_acompanhamento_uf(base="https://resultados.tse.jus.br/oficial/ele2026", ele="544", uf="sp")
    assert url == "https://resultados.tse.jus.br/oficial/ele2026/544/dados/sp/sp-e000544-ab.json"


def test_url_config_eleicoes_formato():
    """EA11 — configuração de eleições (lista turnos)."""
    url = url_config_eleicoes(base="https://resultados.tse.jus.br/oficial")
    assert url == "https://resultados.tse.jus.br/oficial/ele2026/config/"


def test_url_fixos_legado():
    """Mantido para compatibilidade (esquema antigo)."""
    url = url_fixos(base="https://resultados.tse.jus.br/oficial/ele2026", ele="544", cargo="0003")
    assert url == "https://resultados.tse.jus.br/oficial/ele2026/544/config/ele-c0003-e000544-cf.json"


def test_gerar_tarefas_produto_cartesiano():
    """2 UFs x 2 cargos = 4 tarefas."""
    tarefas = gerar_tarefas(ele="544", ufs=["sp", "rj"], cargos=["governador", "presidente"])
    assert len(tarefas) == 4
    streams = [t["stream"] for t in tarefas]
    assert "megatron:sp:governador" in streams
    assert "megatron:sp:presidente" in streams
    assert "megatron:rj:governador" in streams
    assert "megatron:rj:presidente" in streams


def test_gerar_tarefas_listas_tamanhos_diferentes():
    """3 UFs x 2 cargos = 6 tarefas (nao 2, como seria com zip)."""
    tarefas = gerar_tarefas(ele="544", ufs=["sp", "rj", "mg"], cargos=["governador", "presidente"])
    assert len(tarefas) == 6
    pares = {(t["uf"], t["cargo"]) for t in tarefas}
    assert pares == {
        ("sp", "governador"), ("sp", "presidente"),
        ("rj", "governador"), ("rj", "presidente"),
        ("mg", "governador"), ("mg", "presidente"),
    }


def test_gerar_tarefas_deputado_federal():
    """Cenario alvo do MEGATRON: dep_federal para 11 UFs."""
    ufs = ["sp", "rj", "mg", "ba", "rs", "pr", "pe", "ce", "pa", "ma", "go"]
    tarefas = gerar_tarefas(ele="544", ufs=ufs, cargos=["dep_federal"])
    assert len(tarefas) == 11
    for t in tarefas:
        assert "c0006" in t["url"]  # dep_federal sempre codigo 0006
        assert t["url"].endswith("-u.json")  # sufixo unificado
        assert t["stream"].startswith("megatron:")
        assert t["stream"].endswith(":dep_federal")


def test_gerar_tarefas_lista_vazia():
    assert gerar_tarefas(ele="544", ufs=[], cargos=["governador"]) == []
    assert gerar_tarefas(ele="544", ufs=["sp"], cargos=[]) == []