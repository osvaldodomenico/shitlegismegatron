"""
Selecao compartilhada de candidatos a acompanhar (no maximo 5 por corrida).

Motivo de existir: o payload de deputado federal de SP traz 1429 candidatos e
~240 KB, e a resposta da API leva ~1,6s. Reenviar isso a cada ciclo para cada
espectador custa rede e parse no navegador. Aplicando a selecao NO SERVIDOR o
mesmo payload cai para ~2 KB — filtrar so no navegador economizaria render,
nao trafego.

A chave do candidato e `sqcand` (sequencial oficial do TSE), nao `seq`: `seq`
e a posicao dentro do arquivo e pode mudar entre publicacoes, enquanto
`sqcand` identifica o candidato durante toda a eleicao.

A selecao e compartilhada (todos veem a mesma), entao cabe cache em memoria:
o Postgres e a fonte da verdade e o cache evita um SELECT por broadcast.
"""
from typing import Dict, List, Sequence

MAX_SELECIONADOS = 5

# chave "uf:cargo" -> lista de sqcand, na ordem escolhida pelo usuario
_cache: Dict[str, List[str]] = {}


def chave(uf: str, cargo: str) -> str:
    return f"{uf}:{cargo}"


def get(uf: str, cargo: str) -> List[str]:
    """Selecao atual. Lista vazia significa 'sem filtro'."""
    return _cache.get(chave(uf, cargo), [])


def set_cache(uf: str, cargo: str, sqcands: Sequence[str]) -> None:
    """Atualiza o cache. Quem persiste no Postgres e a camada de rotas."""
    _cache[chave(uf, cargo)] = [str(s) for s in sqcands]


def limpar_cache() -> None:
    """Usado nos testes e no startup, antes de recarregar do banco."""
    _cache.clear()


def normalizar(sqcands: Sequence[str]) -> List[str]:
    """
    Remove duplicatas preservando a ordem e corta em MAX_SELECIONADOS.
    Levanta ValueError se vier mais do que o limite, em vez de truncar em
    silencio: truncar esconderia do usuario que a escolha dele foi ignorada.
    """
    vistos: List[str] = []
    for s in sqcands:
        s = str(s).strip()
        if s and s not in vistos:
            vistos.append(s)
    if len(vistos) > MAX_SELECIONADOS:
        raise ValueError(
            f"no maximo {MAX_SELECIONADOS} candidatos por corrida; recebi {len(vistos)}"
        )
    return vistos


def filtrar(payload: dict, sqcands: Sequence[str]) -> dict:
    """
    Copia do payload com `cand` restrito aos sqcand escolhidos, na ordem da
    selecao. Selecao vazia devolve o payload intacto — quem nao escolheu nada
    continua vendo a corrida inteira.

    Os totais da corrida (pst, vv, tv...) sao preservados de proposito: o
    percentual de cada candidato so faz sentido contra o total real.
    """
    if not sqcands:
        return payload
    ordem = {str(s): i for i, s in enumerate(sqcands)}
    escolhidos = [
        c for c in (payload.get("cand") or []) if str(c.get("sqcand")) in ordem
    ]
    escolhidos.sort(key=lambda c: ordem[str(c.get("sqcand"))])
    return {**payload, "cand": escolhidos}


def resumir_candidatos(payload: dict) -> List[dict]:
    """
    Lista enxuta para o seletor: so o que o usuario precisa para escolher.
    1429 candidatos completos sao ~240 KB; so estes campos, ~70 KB.
    """
    return [
        {
            "sqcand": c.get("sqcand"),
            "nm": c.get("nm"),
            "cc": c.get("cc"),
            "n": c.get("n"),
        }
        for c in (payload.get("cand") or [])
    ]
