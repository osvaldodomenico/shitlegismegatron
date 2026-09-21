"""
Indicadores derivados da apuracao proporcional (deputado federal/estadual,
vereador).

DECISAO IMPORTANTE: este modulo NAO reimplementa a distribuicao de vagas.
O calculo legal completo (quociente partidario, sobras por maiores medias em
rodadas sucessivas, barreira de 80% do QE para o partido e 20% para o
candidato — Lei 14.211/2021) e cheio de arestas, e o proprio TSE ja publica a
resposta dele a cada boletim no campo `st` de cada candidato
("Eleito por QP", "Eleito por media", "Suplente", "Nao eleito").
Reimplementar so criaria divergencia com a fonte oficial na hora errada.

O que este modulo acrescenta e o que o TSE NAO entrega mastigado:
  - quociente eleitoral da corrida;
  - barreira individual (10% do QE): abaixo dela o candidato nao se elege,
    por mais vagas que o partido conquiste;
  - LINHA DE CORTE dentro da agremiacao: quantos votos separam o ultimo
    eleito do primeiro suplente. Validado contra a apuracao real de 2022 em
    SP: 8 de 8 agremiacoes com a ordem identica a do TSE.

Cuidado com apuracao parcial: o QE usa os votos validos APURADOS ATE AGORA,
entao ele cresce ao longo da noite. Os numeros sao comparaveis entre si
(votos dos candidatos tambem sao parciais), mas nao sao o QE final —
`parcial` avisa isso a interface.
"""
import os
from collections import defaultdict
from typing import Optional

FATOR_BARREIRA_INDIVIDUAL = 0.10  # Lei 14.211/2021: 10% do quociente eleitoral


def _int(valor) -> int:
    try:
        return int(str(valor).strip() or 0)
    except ValueError:
        return 0


def _num(valor) -> float:
    texto = str(valor or "0").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def quociente_eleitoral(votos_validos: int, vagas: int) -> Optional[int]:
    """
    Codigo Eleitoral, art. 106: votos validos divididos pelas vagas,
    "desprezada a fracao se igual ou inferior a meio, equivalente a um se
    superior". Ou seja, arredondamento para cima so acima de 0,5.
    """
    if not vagas:
        return None
    bruto = votos_validos / vagas
    inteiro = int(bruto)
    return inteiro + (1 if (bruto - inteiro) > 0.5 else 0)


def _eleito(cand: dict) -> bool:
    return str(cand.get("st", "")).strip().lower().startswith("eleito")


def calcular(payload: dict) -> dict:
    """
    Indicadores da corrida e de cada candidato.

    Devolve {} para corridas majoritarias (sem `v`, o numero de vagas), onde
    quociente nao faz sentido.
    """
    vagas = _int(payload.get("v"))
    validos = _int(payload.get("vv"))
    if not vagas or not validos:
        return {}

    qe = quociente_eleitoral(validos, vagas)
    barreira = int(qe * FATOR_BARREIRA_INDIVIDUAL) if qe else 0

    # Votos anulados continuam listados em `cand`, mas nao contam: so a soma
    # dos `dvt == "Válido"` reproduz o `vnom` do payload.
    validos_cand = [
        c for c in (payload.get("cand") or [])
        if str(c.get("dvt", "Válido")).startswith("Válido")
    ]

    por_agremiacao = defaultdict(list)
    for c in validos_cand:
        por_agremiacao[c.get("cc") or "—"].append(c)

    por_candidato = {}
    for _cc, lista in por_agremiacao.items():
        lista.sort(key=lambda c: -_int(c.get("vap")))
        # Vagas da agremiacao: a contagem que o proprio TSE ja publicou.
        # Enquanto nenhum `st` esta preenchido (inicio da apuracao), fica None
        # e a interface mostra "aguardando" em vez de inventar um numero.
        eleitos = sum(1 for c in lista if _eleito(c))
        definido = any(str(c.get("st", "")).strip() for c in lista)
        vagas_agr = eleitos if definido else None

        ultimo_dentro = lista[eleitos - 1] if eleitos else None
        primeiro_fora = lista[eleitos] if len(lista) > eleitos else None

        for i, c in enumerate(lista):
            votos = _int(c.get("vap"))
            dentro = _eleito(c)
            # Margem: quem esta dentro compara com o primeiro de fora; quem
            # esta fora compara com o ultimo de dentro. Sempre "quantos votos
            # me separam da linha".
            if vagas_agr is None:
                margem = None
                referencia = None
            elif dentro:
                margem = votos - _int(primeiro_fora.get("vap")) if primeiro_fora else None
                referencia = primeiro_fora.get("nm") if primeiro_fora else None
            else:
                margem = votos - _int(ultimo_dentro.get("vap")) if ultimo_dentro else None
                referencia = ultimo_dentro.get("nm") if ultimo_dentro else None

            por_candidato[str(c.get("sqcand"))] = {
                "posicao_agremiacao": i + 1,
                "total_agremiacao": len(lista),
                "vagas_agremiacao": vagas_agr,
                "dentro_do_corte": dentro,
                "margem": margem,
                "referencia": referencia,
                "passou_barreira": votos >= barreira if barreira else None,
                "falta_barreira": max(barreira - votos, 0) if barreira else None,
                "situacao": c.get("st") or "",
            }

    return {
        "vagas": vagas,
        "votos_validos": validos,
        "quociente_eleitoral": qe,
        "barreira_individual": barreira,
        "parcial": _num(payload.get("pst")) < 100.0,
        "por_candidato": por_candidato,
    }


# Fotos oficiais: .../oficial/ele<ANO>/<ele>/fotos/<uf>/<sqcand>.jpeg (~6 KB).
# Servidas pela propria CDN do TSE, entao nao passam pela nossa banda.
TSE_FOTOS_BASE = os.environ.get(
    "TSE_FOTOS_BASE", "https://resultados.tse.jus.br/oficial/ele2022"
)


def url_foto(uf: str, ele: str, sqcand: str) -> Optional[str]:
    if not (uf and ele and sqcand):
        return None
    return f"{TSE_FOTOS_BASE}/{ele}/fotos/{uf.lower()}/{sqcand}.jpeg"


def preparar(payload: dict, uf: str, sqcands=None) -> dict:
    """
    Payload pronto para a interface: indicadores calculados sobre a corrida
    INTEIRA e so depois o recorte dos acompanhados.

    A ordem importa — posicao na agremiacao e linha de corte dependem de todos
    os candidatos. Calcular depois de filtrar daria "1o de 5".
    """
    import selecao as sel

    indicadores = calcular(payload)
    recortado = sel.filtrar(payload, sqcands or [])
    por_cand = indicadores.get("por_candidato", {})
    ele = str(payload.get("ele") or "")

    cands = []
    for c in recortado.get("cand") or []:
        sq = str(c.get("sqcand"))
        cands.append({**c, "ind": por_cand.get(sq), "foto": url_foto(uf, ele, sq)})

    resumo = {k: v for k, v in indicadores.items() if k != "por_candidato"}
    return {**recortado, "cand": cands, "indicadores": resumo}
