"""
Templates de URL para o feed oficial do TSE.

Esquema confirmado contra a CDN em producao (probe em 03/10/2026):

    https://resultados.tse.jus.br/oficial/<ciclo>/<ELE>/dados/
        <abr>/<abr>-c<CCCC>-e<ELEICA>-u.json

    200  .../ele2026/6257/dados/br/br-c0001-e006257-u.json
    200  .../ele2026/6259/dados/sp/sp-c0006-e006259-u.json
    404  .../ele2026/6257/dados-simplificados/br/br-c0001-e006257-r.json  (removido)

CORRECAO (21/09/2026): a versao anterior deste arquivo afirmava que o esquema
"dados/<abr>/<abr>-c<CCCC>-e<ELEICA>-u.json" nao existia na CDN. **Existe.**
Probe direto:
    200  .../ele2022/546/dados/sp/sp-c0006-e000546-u.json        (geral)
    200  .../ele2024/619/dados/sp/sp71072-c0011-e000619-u.json   (municipal)

A diferenca real e de cobertura e de formato:
  - `dados-simplificados/...-r.json` existiu na ELEICAO GERAL ate 2022. Payload
    achatado (pst, cand, hg no topo) — era o que este collector lia, e o que
    UOL/G1 consumiam. Em 2026 o TSE REMOVEU esse caminho da CDN (404).
  - `dados/...-u.json` existe nos dois tipos de pleito, com payload ANINHADO
    (`s`, `e`, `v` nos totais; `carg[].agr[].par[].cand[]` nos candidatos) e
    mais rico: traz federacoes, vagas por agremiacao e votos de legenda por
    partido. Nosso fetcher ACHATA esse formato em `tse_nested.achatar` para o
    contrato plano (pst, cand, hg no topo) que a API e a interface consomem.

Por isso o caminho e o sufixo continuam configuraveis por env
(TSE_PATH_DADOS e TSE_SUFIXO): se o TSE reativar o esquema antigo no dia,
da para voltar sem rebuild.

ABRANGENCIA — o TSE usa UM CODIGO DE ELEICAO POR ABRANGENCIA, nao por turno:

    ele=6257 ->  nacional: presidente, publicado sob a abrangencia "br"
    ele=6259 ->  por UF:   governador, senador, dep. federal, dep. estadual
    ele=6260 ->  2o turno de governador (por UF)
    (544/546/547 eram os codigos de 2022, hoje sem arquivo na CDN)

Por isso `gerar_tarefas` recebe dois codigos e so cruza os pares que
existem de fato na CDN (presidente x br; demais cargos x UF).
"""

from __future__ import annotations

import os
from itertools import product

# Configuraveis para nao precisar de rebuild se o TSE mudar o caminho no dia.
PATH_DADOS = os.environ.get("TSE_PATH_DADOS", "dados")
SUFIXO = os.environ.get("TSE_SUFIXO", "u")

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

    Exemplo (presidente 1T 2026, nacional):
        https://resultados.tse.jus.br/oficial/ele2026/6257/dados/br/br-c0001-e006257-u.json

    Exemplo (dep. federal 1T 2026, SP):
        https://resultados.tse.jus.br/oficial/ele2026/6259/dados/sp/sp-c0006-e006259-u.json
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
