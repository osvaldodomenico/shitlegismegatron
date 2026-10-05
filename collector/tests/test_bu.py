import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bu import ler_boletim

AQUI = os.path.dirname(__file__)


def _bu():
    with open(os.path.join(AQUI, "fixtures", "sp71072-z0020-s0100-bu.dat"), "rb") as f:
        return ler_boletim(f.read())


def test_identificacao_da_secao_e_emissao():
    b = _bu()
    assert (b.municipio, b.zona, b.local, b.secao) == (71072, 20, 1074, 100)
    assert b.emissao == "20261004T170734"
    assert b.aptos == {6257: 393, 6259: 393}
    assert b.eleitores_lib_codigo == 278


def test_cinco_cargos_e_comparecimento_fecha_com_os_votos():
    b = _bu()
    cargos = {r.cargo: r for r in b.resultados}
    assert set(cargos) == {"presidente", "governador", "senador", "dep_federal", "dep_estadual"}
    assert all(r.comparecimento == 278 for r in b.resultados)
    assert b.consistente(), {r.cargo: (r.soma(), r.comparecimento) for r in b.resultados}
    assert cargos["presidente"].tipo_cargo == 1 and cargos["dep_federal"].tipo_cargo == 2
    # senador 2026: duas vagas, cada eleitor vota duas vezes
    assert cargos["senador"].votos_por_eleitor == 2 and cargos["senador"].soma() == 556
    assert cargos["presidente"].votos_por_eleitor == 1


def test_votos_do_presidente_batem_com_o_hex_lido_na_mao():
    p = {v.codigo: v for v in _bu().resultados[0].votaveis if v.tipo == "nominal"}
    assert p[13].votos == 0x7C and p[13].partido == 13
    assert p[14].votos == 0x0D and p[22].votos == 0x61
    tipos = {v.tipo: v.votos for v in _bu().resultados[0].votaveis if v.tipo != "nominal"}
    assert tipos == {"branco": 5, "nulo": 15}


def test_proporcional_tem_legenda_e_numero_de_urna():
    fed = next(r for r in _bu().resultados if r.cargo == "dep_federal")
    nominais = [v for v in fed.votaveis if v.tipo == "nominal"]
    legendas = [v for v in fed.votaveis if v.tipo == "legenda"]
    assert any(v.codigo == 1000 and v.partido == 10 for v in nominais)
    assert legendas and all(v.codigo == v.partido for v in legendas)
    assert len(fed.votaveis) == 91
