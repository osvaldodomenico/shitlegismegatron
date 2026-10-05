import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from bi_sync import norm, bruto, titulo, data_br, num_br, pct, idade_em, bi_apagar


def test_formato_padrao_do_bi():
    assert norm("SUPERIOR COMPLETO") == "superior completo"
    assert norm("ELEIÇÃO ORDINÁRIA") == "eleicao ordinaria"
    assert norm("2º SUPLENTE") == "2o suplente"
    assert norm("#NULO") is None and norm("NÃO DIVULGÁVEL") is None and norm("-1") is None
    assert titulo("ANDRÉ AMADO") == "André Amado"
    assert data_br("08/04/1950") == "1950-04-08" and data_br("#NULO") is None
    assert num_br("2125,00") == 2125.0 and num_br("1.234,5") == 1234.5 and num_br("-9,9382839") == -9.9382839
    assert pct(226, 247) == 91.497976 and pct(1, 0) == 0.0
    assert idade_em("1950-04-08") == 76 and idade_em("1965-10-18") == 60


def test_delete_no_bi_sempre_filtra_2026():
    class Falso:
        def cursor(self):
            raise AssertionError("nao deveria chegar aqui")
    with pytest.raises(AssertionError, match="ano = 2026"):
        bi_apagar(Falso(), "DELETE FROM candidatos WHERE sigla_uf = %s", ("SP",))
