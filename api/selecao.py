"""
Selecao compartilhada de candidatos a acompanhar (limite por MAX_SELECIONADOS).

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
import os
import re
from typing import Dict, List, Sequence, Tuple

# Era 5 (cabia no painel). Em 04/10 o Domenico pediu para tirar a trava: o
# limite vira so uma protecao contra payload absurdo, configuravel por env.
MAX_SELECIONADOS = int(os.environ.get("MAX_SELECIONADOS", "50"))

# PERFIS: a mesma corrida pode ter listas de acompanhados independentes —
# "padrao" e a da tela principal e do /painel; "geral" e a do /apuracaogeral.
# Um perfil nao enxerga nem altera o outro.
PERFIL_PADRAO = "padrao"
_PERFIL_VALIDO = re.compile(r"^[a-z0-9_-]{1,32}$")

# chave "uf:cargo:perfil" -> lista de sqcand, na ordem escolhida pelo usuario
_cache: Dict[str, List[str]] = {}


def validar_perfil(perfil: str) -> str:
    """Nome de perfil seguro para virar chave de cache, room e linha no banco."""
    perfil = (perfil or PERFIL_PADRAO).strip().lower()
    if not _PERFIL_VALIDO.match(perfil):
        raise ValueError(f"perfil invalido: {perfil!r} (use a-z, 0-9, '-' ou '_')")
    return perfil


def chave(uf: str, cargo: str, perfil: str = PERFIL_PADRAO) -> str:
    return f"{uf}:{cargo}:{perfil}"


def room(uf: str, cargo: str, perfil: str = PERFIL_PADRAO) -> str:
    """Room do WebSocket da selecao. O perfil padrao mantem o nome antigo."""
    base = f"{uf}:{cargo}:sel"
    return base if perfil == PERFIL_PADRAO else f"{base}:{perfil}"


def get(uf: str, cargo: str, perfil: str = PERFIL_PADRAO) -> List[str]:
    """Selecao atual. Lista vazia significa 'sem filtro'."""
    return _cache.get(chave(uf, cargo, perfil), [])


def set_cache(uf: str, cargo: str, sqcands: Sequence[str], perfil: str = PERFIL_PADRAO) -> None:
    """Atualiza o cache. Quem persiste no Postgres e a camada de rotas."""
    _cache[chave(uf, cargo, perfil)] = [str(s) for s in sqcands]


def perfis_com_selecao(uf: str, cargo: str) -> List[Tuple[str, List[str]]]:
    """(perfil, sqcands) de cada perfil que tem selecao nessa corrida."""
    prefixo = f"{uf}:{cargo}:"
    return [
        (k[len(prefixo):], v) for k, v in _cache.items()
        if k.startswith(prefixo) and v
    ]


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
