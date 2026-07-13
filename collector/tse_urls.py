"""
Templates de URL para o feed oficial do TSE.

Baseado na documentacao oficial "Instrucoes para download dos arquivos da
Divulgacao de resultados das Eleicoes 2024" (TSE, versao 1.1 de 19/08/2024).

Hierarquia do servidor HTTP do TSE (Data Center/CDN):
    http://<host>/[ambiente]/[ciclo]/[eleicao]/
        config/...
        dados/<br|uf|zz>/
            <uf>-c<CCCC>-e<ELEICA>-u.json   <- resultado unificado por UF
            <uf>-c<CCCC>-e<ELEICA>-e.json   <- arquivo de eleitos (EA10)
            <uf>-e<ELEICA>-ab.json          <- acompanhamento UF (EA15)
        fotos/<br|uf|zz>/<sqcand>.jpeg

Em 2026 (ciclo ele2026), o TSE divulga o resultado oficial nesta estrutura.
Cada arquivo de resultado unificado (sufixo -u) traz todos os candidatos do
cargo na UF com votos atualizados — eh o mesmo arquivo que UOL/G1/Estadao
consomem para montar suas paginas de apuracao em tempo real.

Antes deste ajuste, o codigo usava o esquema antigo "dados-simplificados"
que retornava 404 nas eleicoes recentes do TSE.
"""

from itertools import product

# Mapeamento cargo → codigo TSE (4 digitos)
CARGO_CODIGOS = {
    "presidente":   "0001",
    "governador":   "0003",
    "senador":      "0005",
    "dep_federal":  "0006",
    "dep_estadual": "0007",
}


def url_resultado(base: str, ele: str, uf: str, cargo: str) -> str:
    """
    URL de resultado unificado (EA20) por UF/cargo.

    Esquema oficial TSE:
        {base}/{ele}/dados/{uf}/{uf}-c{cargo}-e{ele_padded}-u.json

    Exemplo (1T 2022, SP, governador):
        https://resultados.tse.jus.br/oficial/ele2022/544/dados/sp/sp-c0003-e000544-u.json

    O sufixo -u indica "unificado" — arquivo consolidado com candidatos
    e votos apurados ate o momento.
    """
    ele_padded = str(ele).zfill(6)
    return f"{base}/{ele}/dados/{uf}/{uf}-c{cargo}-e{ele_padded}-u.json"


def url_eleitos(base: str, ele: str, uf: str, cargo: str) -> str:
    """
    URL do arquivo de eleitos (EA10) por UF/cargo.
    Disponivel a partir do momento em que o TSE fecha a apuracao.

    Exemplo:
        https://resultados.tse.jus.br/oficial/ele2022/544/dados/sp/sp-c0003-e000544-e.json
    """
    ele_padded = str(ele).zfill(6)
    return f"{base}/{ele}/dados/{uf}/{uf}-c{cargo}-e{ele_padded}-e.json"


def url_acompanhamento_uf(base: str, ele: str, uf: str) -> str:
    """
    URL de acompanhamento UF (EA15) — historico de totalizacao por UF.
    """
    ele_padded = str(ele).zfill(6)
    return f"{base}/{ele}/dados/{uf}/{uf}-e{ele_padded}-ab.json"


def url_config_eleicoes(base: str, ciclo: str = "ele2026") -> str:
    """
    URL de configuracao de eleicoes (EA11).
    Retorna lista de eleicoes (turnos) com seus codigos numericos.
    """
    return f"{base}/{ciclo}/config/"


def url_fixos(base: str, ele: str, cargo: str) -> str:
    """
    URL de configuracao fixa (metadados de candidatos).

    Mantida por compatibilidade — esquema antigo usava este path.
    Em 2024+ nao ha mais esse arquivo; mantido aqui apenas caso
    outro portal ainda exponha.
    """
    ele_padded = str(ele).zfill(6)
    return f"{base}/{ele}/config/ele-c{cargo}-e{ele_padded}-cf.json"


def gerar_tarefas(ele: str, ufs: list[str], cargos: list[str]) -> list[dict]:
    """
    Retorna lista de dicts com url e stream para cada par UF x cargo.
    Usa itertools.product (cruzamento cartesiano).
    """
    tarefas = []
    for uf, cargo_nome in product(ufs, cargos):
        codigo = CARGO_CODIGOS.get(cargo_nome, "0003")
        tarefas.append({
            "url": url_resultado(base="{base}", ele=ele, uf=uf, cargo=codigo),
            "stream": f"megatron:{uf}:{cargo_nome}",
            "uf": uf,
            "cargo": cargo_nome,
        })
    return tarefas