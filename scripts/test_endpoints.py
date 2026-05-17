#!/usr/bin/env python3
"""
Smoke test: verifica se todos os serviços da stack MEGATRON estão respondendo.
Executar com a stack rodando: docker compose --profile dev up -d
"""
import sys
import httpx

BASE_API = "http://localhost:8000"
BASE_SIM = "http://localhost:8001"

CHECKS = [
    (f"{BASE_API}/health",                          "API health"),
    (f"{BASE_SIM}/health",                          "Simulator health"),
    (f"{BASE_API}/resultados/sp/governador",        "API resultados (pode ser 404 se sem dados)"),
    (f"{BASE_API}/historico/sp/governador",         "API historico"),
]

def run() -> bool:
    ok = True
    for url, label in CHECKS:
        try:
            r = httpx.get(url, timeout=5)
            status = "✅" if r.status_code < 500 else "❌"
            print(f"  {status} {label}: HTTP {r.status_code}")
            if r.status_code >= 500:
                ok = False
        except Exception as e:
            print(f"  ❌ {label}: {e}")
            ok = False
    return ok

if __name__ == "__main__":
    print("🔍 MEGATRON Smoke Test\n")
    if run():
        print("\n✅ Todos os checks passaram.")
        sys.exit(0)
    else:
        print("\n❌ Alguns checks falharam.")
        sys.exit(1)
