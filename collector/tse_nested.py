"""
Achata o payload ANINHADO do TSE (`dados/<abr>/<abr>-c<CCCC>-e<ELE>-u.json`)
para o contrato PLANO que a API, a selecao e a interface ja consomem.

Por que existe (03/10/2026, verificado na CDN):

O esquema `dados-simplificados/...-r.json`, que o collector lia ate ontem, foi
REMOVIDO do CDN do TSE. Todas as URLs do escopo de 04/10 com esse esquema
respondem 404 — probe:

    404  .../ele2026/6257/dados-simplificados/br/br-c0001-e006257-r.json
    404  .../ele2026/6259/dados-simplificados/sp/sp-c0006-e006259-r.json
    404  .../ele2022/546/dados-simplificados/sp/sp-c0006-e000546-r.json

O esquema que responde 200 e o completo, aninhado:

    200  .../ele2026/6257/dados/br/br-c0001-e006257-u.json
    200  .../ele2026/6259/dados/sp/sp-c0006-e006259-u.json   (230 KB, 45+5 cand)

No payload aninhado os totais ficam em blocos nomeados (`s`, `e`, `v`) e os
candidatos em `carg[].agr[].par[].cand[]`; `pst` e `cand` no TOPO ficam VAZIOS
(`pst: 0`, `cand: []`) porque ali so mora a metadado da geraracao. Um fetcher
que so exige `pst`/`cand` no topo aceitaria o arquivo e publicaria uma
corrida sem nenhum candidato — o pior tipo de bug: 200 OK, tela viva, zero
dado. Por isso a validacao deste modulo e ESTRUTURAL, nao so de chaves.

O achatamento e uma traducao de nomes, sem recalcular nada:

    s.pst        -> pst    (percentual de secoes totalizadas)
    v.vv         -> vv     (votos validos)
    v.vnom       -> vnom   (soma dos `dvt == "Válido"`; confere com o TSE)
    v.tv         -> v      (vagas — proporcional; ausente em majoritaria)
    e.e          -> e      (eleitorado)
    cand.nm/nmu  -> nm/nmu ; vap -> vap ; pvap -> pvap ; st -> st
    par.sg       -> cc     (partido do candidato, estava na flat 2022)
    agr.vag      -> vagas_agr (vagas da agremiacao, contagem do proprio TSE)

`dvt` nao vem no aninhado: o TSE marca `cand[].e == "s"` para voto anulado/suspenso.
Traduzimos isso para `dvt` porque `api.apuracao` filtra os anulados por `dvt`
(reproduzir o `vnom` do TSE e o que valida o calculo de quociente).
"""

from __future__ import annotations

# Campos do topo que a flat 2022 trazia soltos.
_TOTAL_VOTOS = "e"      # eleitorado
_TOTAL_VOTOS_VALIDOS = "v"


def _texto(valor) -> str:
    """Normaliza qualquer valor do TSE para string, nunca None.

    A flat trazia tudo como string ("0", "100,00"). `api` e `selecao`
    comparam com `str(...)`, mas o `None` escapando aqui viraria `cc: None`
    na lista de candidatos — e o agrupamento por agremiacao usaria o
    placeholder "—" para candidatos cujo partido nao foi lido.
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return ""
    if isinstance(valor, float):
        # TSE publica "100,00"; float so aparece se o JSON vier tipado.
        return f"{valor:.2f}".replace(".", ",")
    return str(valor)


def _voto_anulado(cand: dict) -> str:
    """
    Traduz `cand[].e` para `dvt`.

    No aninhado o TSE nao manda `dvt`: marca voto anulado/suspenso em
    `cand[].e` ("n" = não, "s" = sim). Confirmado em 2024:
    `cand[].e == "s"` com `dvt: "Anulado"` no arquivo equivalente de 2022.
    Sem esta traducao, `apuracao.calcular` somaria votos anulados no quociente.
    """
    return "Anulado" if _texto(cand.get("e")).strip().lower() == "s" else "Válido"


def achatar(payload: dict) -> dict:
    """
    Converte o payload aninhado do TSE no contrato plano da API.

    Idempotente: um payload ja achatado (ou o do simulador) passa intacto,
    para que o mesmo fetcher sirva os dois formatos. A deteccao e por
    presenca de `carg` com `agr`/`par` aninhado — nao por `pst`/`cand` no
    topo, porque no arquivo aninhado eles EXISTEM e valem vazio.
    """
    cargos = payload.get("carg") or []
    aninhado = any(
        (c.get("agr") or [])
        and any((a.get("par") or []) for a in (c.get("agr") or []))
        for c in cargos
    )
    if not aninhado:
        return payload

    # ---- totais: os blocos nomeados sobem para o topo, com os mesmos nomes
    # que a flat usava. `v` e a lista de vagas do TSE; para a flat era o
    # inteiro. `apuracao` so le `v` como numero de vagas.
    s = payload.get("s") or {}
    e = payload.get("e") or {}
    v = payload.get("v") or {}

    flat: dict = dict(payload)
    flat.pop("carg", None)
    flat["pst"] = _texto(s.get("pst"))
    flat["e"] = _texto(e.get("e") or e.get("te"))
    flat["vv"] = _texto(v.get("vv"))
    flat["vnom"] = _texto(v.get("vnom"))
    flat["v"] = _texto(v.get("tv"))
    flat["cand"] = _candidatos(cargos)
    flat["vagas_por_agremiacao"] = _vagas_por_agremiacao(cargos)
    return flat


def _candidatos(cargos: list[dict]) -> list[dict]:
    """
    Achata `carg[].agr[].par[].cand[]` numa lista plana de candidatos.

    Cada candidato ganha `cc` (partido) e `ccd` (partido em codigo, `par[].n`),
    que a flat 2022 trazia: `selecao.resumir_candidatos` expoe `cc` no seletor e
    `apuracao.calcular` agrupa por `cc` para ordenar a agremiacao.
    """
    saida: list[dict] = []
    for cargo in cargos:
        for agr in cargo.get("agr") or []:
            for par in agr.get("par") or []:
                partido_cod = _texto(par.get("n"))
                partido_sig = _texto(par.get("sg"))
                for cand in par.get("cand") or []:
                    saida.append(
                        {
                            **cand,
                            "cc": partido_sig,
                            "ccd": partido_cod,
                            "dvt": _voto_anulado(cand),
                        }
                    )
    return saida


def _vagas_por_agremiacao(cargos: list[dict]) -> dict:
    """
    `agr[].vag` — vagas que o TSE atribui a cada agremiacao.

    Fica no topo do payload achatado, e nao dentro do candidato: e um dado da
    corrida, nao de um candidato. `apuracao` ainda prefere a contagem de
    `st` (eleitos) e usa `vag` como referencia do TSE; publicar os dois deixa a
    divergencia visivel se um dia o TSE e a conta nossa divergirem.
    """
    out: dict[str, int] = {}
    for cargo in cargos:
        for agr in cargo.get("agr") or []:
            vag = agr.get("vag")
            if vag is None:
                continue
            try:
                out[_texto(agr.get("n"))] = int(str(vag).strip())
            except (TypeError, ValueError):
                continue
    return out


def tem_dado(payload: dict) -> bool:
    """
    O arquivo existe mas ainda sem apuracao (eleicao ainda nao ocorreu).

    Verificado em 02/10/2026 para o ciclo 6259: `hg` tem hora, `s.pst` vale
    "0,00" e `cand` esta vazio no topo. Publicar esse arquivo seria publicar
    uma corrida com zero candidato, que a interface mostra como "sem dados" a
    cada 60 s. O collector so publica quando ha pelo menos um candidato.
    """
    return len(payload.get("cand") or []) > 0