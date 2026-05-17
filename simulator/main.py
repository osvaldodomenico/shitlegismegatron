"""
Simulador local da CDN do TSE.
Expõe os mesmos endpoints que o TSE real usaria para 2026.
Ativado apenas em modo dev (docker compose --profile dev).
"""
import os
from fastapi import FastAPI
from generator import gerar_resultado

app = FastAPI(title="MEGATRON Simulator")

@app.get("/health")
def health():
    return {"status": "ok", "mode": "MEGATRON_SIM"}

@app.get("/oficial/ele2026/{ele}/dados-simplificados/{uf}/{filename}")
def resultado_variavel(ele: str, uf: str, filename: str):
    """
    Imita o endpoint de dados-simplificados do TSE.
    Extrai cargo do filename: {uf}-c{cargo}-e{ele}-r.json
    Ex: sp-c0003-e000001-r.json → cargo = "0003"
    """
    try:
        # filename: sp-c0003-e000001-r.json
        parts = filename.replace(".json", "").split("-")
        # parts = ["sp", "c0003", "e000001", "r"]
        cargo = parts[1].lstrip("c")  # "0003"
    except (IndexError, ValueError):
        cargo = "governador"
    return gerar_resultado(uf=uf, cargo=cargo)

@app.get("/oficial/ele2026/{ele}/config/{filename}")
def config_fixo(ele: str, filename: str):
    """Retorna config estática (metadados de candidatos)."""
    return {
        "ele": ele,
        "cargos": [
            {"cd": "0001", "ds": "PRESIDENTE"},
            {"cd": "0003", "ds": "GOVERNADOR"},
        ],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
