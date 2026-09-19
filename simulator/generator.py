"""
Gera resultados eleitorais sinteticos com progressao 0% -> 100%.

O payload replica o formato REAL do TSE (dados-simplificados, sufixo -r),
conferido contra a CDN em producao:

    https://resultados.tse.jus.br/oficial/ele2022/544/dados-simplificados/br/br-c0001-e000544-r.json

Pontos do formato real que o simulador respeita (e que a versao anterior
inventava, quebrando o pipeline inteiro):

  - estrutura PLANA: `cand` fica no topo, nao aninhado em `e[0].c`
  - `pst` e `pvap` usam VIRGULA decimal e NAO tem o sinal "%"  ("48,43")
  - `e` no topo eh o total de eleitores aptos (STRING), nao uma lista
  - hora da geracao eh `hg` (e `ht` da totalizacao), nao `hor`
  - `vap` (votos apurados) eh string

DURACAO_SIMULACAO (segundos) controla a velocidade da simulacao.
"""
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

DURACAO = int(os.getenv("DURACAO_SIMULACAO", "3600"))
FIXTURES = Path(__file__).parent / "fixtures"

with open(FIXTURES / "candidatos.json") as f:
    CANDIDATOS = json.load(f)

# Total de eleitores aptos por UF simulada (ordem de grandeza realista).
ELEITORADO = 34_000_000

_inicio = time.time()


def _progresso() -> float:
    """Retorna float 0.0..1.0 representando % da simulacao completa."""
    return min((time.time() - _inicio) / DURACAO, 1.0)


def _br(valor: float, casas: int = 2) -> str:
    """Formata numero no padrao TSE: virgula decimal, sem sinal de %."""
    return f"{valor:.{casas}f}".replace(".", ",")


def gerar_resultado(uf: str = "sp", cargo: str = "0003") -> dict:
    """
    Retorna um payload no mesmo formato que o TSE publica em
    dados-simplificados/<abr>/<abr>-c<cargo>-e<ele>-r.json.
    """
    prog = _progresso()
    pst = prog * 100

    random.seed(int(pst * 100))

    aptos = ELEITORADO
    comparecimento = int(aptos * 0.79 * prog)
    brancos = int(comparecimento * 0.016)
    nulos = int(comparecimento * 0.028)
    validos = comparecimento - brancos - nulos

    pesos = [random.random() for _ in CANDIDATOS]
    soma = sum(pesos)
    votos = [int(p / soma * validos) for p in pesos]

    lider = max(range(len(votos)), key=lambda i: votos[i]) if validos else 0

    cands = [
        {
            "seq": str(i + 1),
            "sqcand": c["sqcand"],
            "n": c["n"],
            "nm": c["nm"],
            "cc": c["sg"],
            "nv": "",
            "e": "s" if i == lider and prog > 0.5 else "n",
            "st": ("Eleito" if i == lider else "Não eleito") if prog > 0.5 else "",
            "dvt": "Válido",
            "vap": str(votos[i]),
            "pvap": _br(votos[i] / validos * 100) if validos else "0,00",
        }
        for i, c in enumerate(CANDIDATOS)
    ]

    agora = datetime.now()
    return {
        "ele": "001",
        "tpabr": "br" if uf == "br" else "uf",
        "cdabr": uf.upper() if uf != "br" else "br",
        "carper": cargo,
        "md": "S",
        "t": "1",
        "f": "o",
        "dg": agora.strftime("%d/%m/%Y"),
        "hg": agora.strftime("%H:%M:%S"),
        "dt": agora.strftime("%d/%m/%Y"),
        "ht": agora.strftime("%H:%M:%S"),
        "pst": _br(pst),
        "e": str(aptos),
        "c": str(comparecimento),
        "pc": _br(comparecimento / aptos * 100) if aptos else "0,00",
        "a": str(aptos - comparecimento),
        "pa": _br((aptos - comparecimento) / aptos * 100) if aptos else "0,00",
        "vb": str(brancos),
        "pvb": _br(brancos / comparecimento * 100) if comparecimento else "0,00",
        "vn": str(nulos),
        "pvn": _br(nulos / comparecimento * 100) if comparecimento else "0,00",
        "vv": str(validos),
        "tv": str(comparecimento),
        "cand": cands,
    }
