"""
Entry point do coletor MEGATRON.
APScheduler executa ciclo_coleta a cada INTERVALO segundos.
Após 10 tentativas falhas de conexão Redis, exit(1) para restart pelo Docker.
"""
import asyncio
import json
import os
import sys
import time

import httpx
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fetcher import fetch_if_changed
from publisher import publish
from tse_urls import gerar_tarefas, CARGO_CODIGOS

TSE_BASE_URL = os.environ["TSE_BASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
# Codigos de eleicao do TSE. O TSE usa um codigo por ABRANGENCIA:
#   ELE_1T     -> eleicoes por UF   (governador, senador, dep. federal/estadual)
#   ELE_1T_BR  -> eleicao nacional  (presidente, abrangencia "br")
# Se ELE_1T_BR nao for definido, cai no mesmo valor de ELE_1T.
ELE_1T = os.environ.get("ELE_1T", "001")
ELE_1T_BR = os.environ.get("ELE_1T_BR") or ELE_1T
INTERVALO = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

# Chave observada pelo healthcheck do Docker e pelo vigia de producao.
HEARTBEAT = "megatron:heartbeat:collector"

_ufs_raw = os.environ.get("UFS", "sp,rj,mg")
_cargos_raw = os.environ.get("CARGOS", "governador")
UFS = [u.strip() for u in _ufs_raw.split(",")]
CARGOS = [c.strip() for c in _cargos_raw.split(",")]

TAREFAS = gerar_tarefas(
    ele=ELE_1T, ufs=UFS, cargos=CARGOS, ele_nacional=ELE_1T_BR
)


async def ciclo_coleta(redis: aioredis.Redis, client: httpx.AsyncClient) -> None:
    """
    Coleta dados de todas as URLs e publica mudancas no Redis.

    O cliente HTTP e criado UMA vez e reaproveitado entre ciclos. Antes era
    um `AsyncClient` novo por ciclo, o que descartava o cookie de sessao do
    WAF do TSE (F5 BIG-IP, `Set-Cookie: TS...`) e refazia o handshake TLS a
    cada rodada: na noite da apuracao, cada poll chegaria como um cliente
    novo e desconhecido, justo quando a protecao esta mais sensivel.

    As URLs sao buscadas em sequencia de proposito — disparar todas de uma
    vez viraria uma rajada contra a mesma origem a cada intervalo.
    """
    publicados = 0
    falhas = 0
    for tarefa in TAREFAS:
        url = tarefa["url"].replace("{base}", TSE_BASE_URL)
        data = await fetch_if_changed(client, url)
        if data:
            await publish(redis, tarefa["stream"], data)
            publicados += 1
        elif not await _url_ok(client, url):
            falhas += 1

    # Batimento cardiaco. "Dado parado" NAO distingue collector vivo de morto:
    # o fetcher so publica quando o payload muda, entao sobre fonte estatica o
    # silencio e legitimo. Este heartbeat e escrito a cada ciclo, com ou sem
    # publicacao, e e o que o healthcheck e o vigia observam.
    await redis.set(
        HEARTBEAT,
        json.dumps({
            "ts": int(time.time()),
            "intervalo": INTERVALO,
            "tarefas": len(TAREFAS),
            "publicados": publicados,
            "falhas": falhas,
        }),
    )
    print(f"[collector] ciclo ok | tarefas={len(TAREFAS)} "
          f"publicados={publicados} falhas={falhas}")


async def _url_ok(client: httpx.AsyncClient, url: str) -> bool:
    """
    Distingue "nada mudou" de "a URL quebrou". `fetch_if_changed` devolve None
    nos dois casos; sem essa checagem, um 404 em todas as corridas — codigo de
    eleicao errado no dia — passaria como silencio normal.
    """
    try:
        r = await client.head(url, timeout=8)
        return r.status_code == 200
    except Exception:
        return False


async def conectar_redis(max_tentativas: int = 10) -> aioredis.Redis:
    """Conecta ao Redis com retry exponencial. Exit(1) após max_tentativas."""
    delay = 1
    for tentativa in range(1, max_tentativas + 1):
        try:
            r = aioredis.from_url(REDIS_URL)
            await r.ping()
            print(f"[collector] Redis conectado após {tentativa} tentativa(s).")
            return r
        except Exception as e:
            print(f"[collector] Redis indisponível (tentativa {tentativa}/{max_tentativas}): {e}")
            if tentativa == max_tentativas:
                print("[collector] Limite de tentativas atingido. Encerrando.")
                sys.exit(1)
            await asyncio.sleep(min(delay, 60))
            delay *= 2


async def main() -> None:
    redis = await conectar_redis()
    # limits: conexoes mantidas vivas entre ciclos (keep-alive), para nao
    # reabrir TLS contra o TSE a cada intervalo.
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=300.0),
        follow_redirects=True,
    )
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        ciclo_coleta,
        "interval",
        seconds=INTERVALO,
        args=[redis, client],
        max_instances=1,
    )
    scheduler.start()
    print(
        f"[collector] Iniciado. Intervalo: {INTERVALO}s | Tarefas: {len(TAREFAS)} "
        f"| ELE_1T={ELE_1T} ELE_1T_BR={ELE_1T_BR}"
    )
    if not TAREFAS:
        print(
            "[collector] AVISO: nenhuma tarefa gerada. Presidente exige 'br' em "
            "UFS; governador/senador/deputados exigem siglas de UF.",
            file=sys.stderr,
        )
    for t in TAREFAS:
        print(f"  → {t['stream']}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
