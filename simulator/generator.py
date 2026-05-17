"""
Gera resultados eleitorais sintéticos com progressão 0% → 100%.
DURACAO_SIMULACAO (segundos) controla a velocidade da simulação.
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

_inicio = time.time()

def _progresso() -> float:
    """Retorna float 0.0..1.0 representando % da simulação completa."""
    return min((time.time() - _inicio) / DURACAO, 1.0)

def gerar_resultado(uf: str = "sp", cargo: str = "governador") -> dict:
    """
    Retorna um payload no mesmo formato que o TSE usa em dados-simplificados.
    Campos principais:
      pst  — % de seções apuradas (string "XX.XX%")
      hor  — hora da última atualização
      e    — lista de municípios/estado com votos por candidato
    """
    prog = _progresso()
    pst = prog * 100

    random.seed(int(pst * 100))

    total_votos = int(prog * 1_000_000)
    votos = [random.random() for _ in CANDIDATOS]
    soma = sum(votos)
    votos = [int(v / soma * total_votos) for v in votos]

    cands = [
        {
            **c,
            "vap": votos[i],
            "pvap": f"{votos[i] / total_votos * 100:.2f}%" if total_votos else "0.00%",
            "e": "Eleito" if i == 0 and prog > 0.5 else "Não eleito",
        }
        for i, c in enumerate(CANDIDATOS)
    ]

    return {
        "cdabr": uf,
        "dv": datetime.now().strftime("%d/%m/%Y"),
        "hor": datetime.now().strftime("%H:%M:%S"),
        "pst": f"{pst:.2f}%",
        "e": [
            {
                "cd": uf,
                "nm": f"{uf.upper()} (SIMULADO)",
                "c": cands,
            }
        ],
    }
