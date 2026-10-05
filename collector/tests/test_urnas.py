import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from urnas import url_aux, url_arquivo, caminho_local, arquivos_do_aux

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
HX = "34364e52686d78713672705759444c2d326f4f495134554d6b4b7341674e4957766831416a35464d5177513d"


def test_urls_da_urna_seguem_o_esquema_confirmado_em_04_10():
    assert url_aux(BASE, "3220", "sp", "71072", 20, 100) == \
        f"{BASE}/arquivo-urna/3220/dados/sp/71072/0020/0100/p03220-sp-m71072-z0020-s0100-aux.json"
    assert url_arquivo(BASE, "3220", "sp", "71072", 20, 100, HX, "o03220sp7107200200100-bu.dat") == \
        f"{BASE}/arquivo-urna/3220/dados/sp/71072/0020/0100/{HX}/o03220sp7107200200100-bu.dat"
    # codigos vindos do cadastro sem zero a esquerda
    assert url_aux(BASE, "3220", "sp", "1392", 1, 686).endswith("/01392/0001/0686/p03220-sp-m01392-z0001-s0686-aux.json")


def test_caminho_local_espelha_a_hierarquia():
    assert caminho_local(Path("/dados/urnas"), "sp", "71072", 20, 100, "x-bu.dat") == \
        Path("/dados/urnas/sp/71072/0020/0100/x-bu.dat")


def test_arquivos_do_aux_le_o_primeiro_bloco():
    aux = {"st": "Recebida", "hashes": [{"hash": HX, "dr": "04/10/2026", "hr": "18:29:49", "st": "Recebido",
            "arq": [{"nm": "a-bu.dat", "tp": "bu"}, {"nm": "a-imgbu.dat", "tp": "imgbu"}, {"nm": "", "tp": "x"}]}]}
    h, lista = arquivos_do_aux(aux)
    assert h == HX and lista == [{"tipo": "bu", "nome": "a-bu.dat"}, {"tipo": "imgbu", "nome": "a-imgbu.dat"}]
    assert arquivos_do_aux({"st": "Nao recebida"}) == (None, [])
