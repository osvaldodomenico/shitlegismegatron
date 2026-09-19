"""
Simulador local da CDN do TSE.
Expoe os mesmos paths que o TSE real publica em producao.
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
    Imita o endpoint dados-simplificados do TSE (o que UOL/G1 consomem).
    Extrai o cargo do filename: {uf}-c{cargo}-e{ele}-r.json
    Ex: sp-c0003-e000001-r.json -> cargo = "0003"
    """
    try:
        # filename: sp-c0003-e000001-r.json
        parts = filename.replace(".json", "").split("-")
        # parts = ["sp", "c0003", "e000001", "r"]
        cargo = parts[1].lstrip("c")  # "0003"
    except (IndexError, ValueError):
        cargo = "0003"
    return gerar_resultado(uf=uf, cargo=cargo)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
