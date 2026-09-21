#!/usr/bin/env python3
"""
Healthcheck do collector, chamado pelo Docker.

Observa o heartbeat que o ciclo grava no Redis. Fica doente se:
  - nao ha heartbeat (nunca completou um ciclo), ou
  - o heartbeat esta velho demais (travou sem morrer — o caso que `restart:
    unless-stopped` sozinho NAO cobre), ou
  - TODAS as URLs falharam no ultimo ciclo (tipicamente codigo de eleicao
    errado ou a CDN fora).

Tolerancia: 3 intervalos. Menos que isso alarmaria por uma lentidao da CDN.
"""
import json
import os
import sys

import redis

CHAVE = "megatron:heartbeat:collector"
TOLERANCIA_CICLOS = 3


def main() -> int:
    try:
        r = redis.from_url(os.environ["REDIS_URL"], socket_timeout=5)
        bruto = r.get(CHAVE)
    except Exception as e:
        print(f"redis indisponivel: {e}")
        return 1

    if not bruto:
        print("sem heartbeat: nenhum ciclo concluido ainda")
        return 1

    hb = json.loads(bruto)
    import time
    idade = int(time.time()) - int(hb.get("ts", 0))
    limite = int(hb.get("intervalo", 60)) * TOLERANCIA_CICLOS

    if idade > limite:
        print(f"heartbeat velho: {idade}s (limite {limite}s) — ciclo travado")
        return 1

    tarefas, falhas = int(hb.get("tarefas", 0)), int(hb.get("falhas", 0))
    if tarefas and falhas >= tarefas:
        print(f"todas as {tarefas} URLs falharam — codigo de eleicao errado ou CDN fora")
        return 1

    print(f"ok: heartbeat com {idade}s, {tarefas} tarefas, {falhas} falha(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
