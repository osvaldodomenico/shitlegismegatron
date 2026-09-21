"""
Templates de URL para o feed oficial do TSE.

Esquema confirmado contra a CDN em producao (probe em 19/09/2026):

    https://resultados.tse.jus.br/oficial/<ciclo>/<ELE>/dados-simplificados/
        <abr>/<abr>-c<CCCC>-e<ELEICA>-r.json

    200  .../ele2022/544/dados-simplificados/br/br-c0001-e000544-r.json
    200  .../ele2022/546/dados-simplificados/sp/sp-c0003-e000546-r.json

CORRECAO (21/09/2026): a versao anterior deste arquivo afirmava que o esquema
"dados/<abr>/<abr>-c<CCCC>-e<ELEICA>-u.json" nao existia na CDN. **Existe.**
Probe direto:
    200  .../ele2022/546/dados/sp/sp-c0006-e000546-u.json        (geral)
    200  .../ele2024/619/dados/sp/sp71072-c0011-e000619-u.json   (municipal)

A diferenca real e de cobertura e de formato:
  - `dados-simplificados/...-r.json` so existe na ELEICAO GERAL. Payload
    achatado (pst, cand, hg no topo) — e o que este collector le, e o que
    UOL/G1 consomem para montar suas paginas.
  - `dados/...-u.json` existe nos dois tipos de pleito, com payload ANINHADO
    (`abr[0]` carrega os totais; dentro, `carg[].agr[].par[].cand[]`) e mais
    rico: traz federacoes, vagas por agremiacao e votos de legenda por
    partido. Nosso parser NAO le esse formato hoje.

Por isso o caminho e o sufixo sao configuraveis por env (TSE_PATH_DADOS e
TSE_SUFIXO): se em 04/10 o TSE publicar so o esquema completo, da para
apontar para ele sem rebuild enquanto o parser e ajustado.

ABRANGENCIA — o TSE usa UM CODIGO DE ELEICAO POR ABRANGENCIA, nao por turno:

    ele=544  ->  nacional: presidente, publicado sob a abrangencia "br"
    ele=546  ->  por UF:   governador, senador, dep. federal, dep. estadual
    ele=547  ->  2o turno de governador (por UF)

Por isso `gerar_tarefas` recebe dois codigos e so cruza os pares que
existem de fato na CDN (presidente x br; demais cargos x UF).
"""

from __future__ import annotations

import os
from itertools import product

# Configuraveis para nao precisar de rebuild se o TSE mudar o caminho no dia.
PATH_DADOS = os.environ.get("TSE_PATH_DADOS", "dados-simplificados")
SUFIXO = os.environ.get("TSE_SUFIXO", "r")

# Mapeamento cargo → codigo TSE (4 digitos)
CARGO_CODIGOS = {
    "presidente":   "0001",
    "governador":   "0003",
    "senador":      "0005",
    "dep_federal":  "0006",
    "dep_estadual": "0007",
}

# Cargos publicados sob a abrangencia nacional ("br"), com codigo de
# eleicao proprio. Todos os demais sao publicados por UF.
CARGOS_NACIONAIS = frozenset({"presidente"})


def url_resultado(base: str, ele: str, uf: str, cargo: str) -> str:
    """
    URL do resultado por abrangencia/cargo.

    Esquema oficial TSE (caminho e sufixo vem de env — ver topo do modulo):
        {base}/{ele}/{PATH_DADOS}/{uf}/{uf}-c{cargo}-e{ele_padded}-{SUFIXO}.json

    Exemplo (presidente 1T 2022, nacional):
        https://resultados.tse.jus.br/oficial/ele2022/544/dados-simplificados/br/br-c0001-e000544-r.json

    Exemplo (governador 1T 2022, SP):
        https://resultados.tse.jus.br/oficial/ele2022/546/dados-simplificados/sp/sp-c0003-e000546-r.json
    """
    ele_padded = str(ele).zfill(6)
    return (
        f"{base}/{ele}/{PATH_DADOS}/{uf}/"
        f"{uf}-c{cargo}-e{ele_padded}-{SUFIXO}.json"
    )


def gerar_tarefas(
    ele: str,
    ufs: list[str],
    cargos: list[str],
    ele_nacional: str | None = None,
) -> list[dict]:
    """
    Cruza UFs x cargos, descartando os pares que nao existem na CDN do TSE.

    - `ele`          codigo da eleicao por UF (governador, senador, deputados)
    - `ele_nacional` codigo da eleicao nacional (presidente); default = `ele`

    Pares descartados:
      - cargo nacional (presidente) em abrangencia que nao seja "br"
      - cargo de UF (governador, senador, ...) na abrangencia "br"
    Ambos retornariam 404.
    """
    ele_nacional = ele_nacional or ele
    tarefas = []
    for uf, cargo_nome in product(ufs, cargos):
        eh_nacional = cargo_nome in CARGOS_NACIONAIS
        eh_abr_br = uf == "br"
        if eh_nacional != eh_abr_br:
            continue
        codigo = CARGO_CODIGOS.get(cargo_nome, "0003")
        ele_alvo = ele_nacional if eh_nacional else ele
        tarefas.append({
            "url": url_resultado(base="{base}", ele=ele_alvo, uf=uf, cargo=codigo),
            "stream": f"megatron:{uf}:{cargo_nome}",
            "uf": uf,
            "cargo": cargo_nome,
        })
    return tarefas
