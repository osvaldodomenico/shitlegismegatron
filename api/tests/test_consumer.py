import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

import pytest
from consumer import parse_pst


@pytest.mark.parametrize("entrada,esperado", [
    ("100,00", 100.0),   # formato real do TSE
    ("48,43", 48.43),
    ("0,00", 0.0),
    ("1.234,56", 1234.56),  # ponto como separador de milhar
    ("100.00%", 100.0),  # formato legado do simulador antigo
    ("73.45%", 73.45),
])
def test_parse_pst_formatos_aceitos(entrada, esperado):
    assert parse_pst(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "abc", "--"])
def test_parse_pst_entrada_invalida_nao_explode(entrada):
    """Antes, float('100,00') levantava ValueError e o INSERT era perdido."""
    assert parse_pst(entrada) == 0.0
