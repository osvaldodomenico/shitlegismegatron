"""
Fetch com diff-hash: só retorna dados se houve mudança desde a última coleta.
Evita publicações e writes desnecessários no Redis.
Valida schema mínimo do TSE; loga alerta se estrutura mudou.
"""
import hashlib
import json
import sys
from typing import Optional

import httpx

from tse_nested import achatar, tem_dado

HEADERS = {
    "User-Agent": "Megatron/1.0 (Election Monitor)",
    "Accept": "application/json",
    "Referer": "https://resultados.tse.jus.br/",
}

# Campos obrigatorios no payload PLANO do TSE — o contrato que a API, a
# selecao e a interface consomem.
#
# Confirmados contra a CDN em 03/10/2026, com o esquema `dados/...-u.json`
# (aninhado, o unico que o TSE ainda serve — ver tse_nested):
#   pst  -> % de secoes totalizadas, string com virgula decimal ("100,00")
#   cand -> lista de candidatos no TOPO do payload (nao aninhada)
#   hg   -> hora da geracao do arquivo ("12:07:13")
#
# Estes chaves sao validadas DEPOIS do achatar. Validar antes aceitaria o
# arquivo aninhado — onde `pst` e `cand` existem no topo mas valem vazio — e
# publicaria uma corrida sem candidato nenhum.
REQUIRED_KEYS = frozenset({"pst", "cand", "hg"})

# Cache em memória: url → MD5 hash do último payload
_snapshots: dict[str, str] = {}


def _hash(data: dict) -> str:
    return hashlib.md5(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


async def fetch_if_changed(client: httpx.AsyncClient, url: str) -> Optional[dict]:
    """
    Faz GET na URL. Retorna o payload se houve mudança desde a última chamada.
    Retorna None se os dados são idênticos, schema inválido, ou se houve erro.
    """
    try:
        r = await client.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        # O TSE serve o arquivo ANINHADO (`dados/...-u.json`). Achatar aqui
        # deixa o resto da cadeia — publisher, consumer, apuracao, interface —
        # falando o mesmo contrato plano de sempre.
        data = achatar(r.json())
        # Schema validator: alerta se campos obrigatórios estão ausentes
        if not REQUIRED_KEYS.issubset(data.keys()):
            print(
                f"[fetcher] WARNING schema inesperado em {url}: "
                f"keys={list(data.keys())}",
                file=sys.stderr,
            )
            return None
        # Arquivo publicado mas sem apuracao (eleicao ainda nao ocorreu): o TSE
        # gera o .json com a lista de candidatos vazia e `pst` = 0,00. Publicar
        # isso seria publicar uma corrida com zero candidato — a interface
        # mostraria "sem dados" a cada 60 s em vez de continuar vazia.
        if not tem_dado(data):
            return None
        h = _hash(data)
        if _snapshots.get(url) == h:
            return None
        _snapshots[url] = h
        return data
    except Exception as exc:
        print(f"[fetcher] ERRO ao buscar {url}: {exc}")
        return None
