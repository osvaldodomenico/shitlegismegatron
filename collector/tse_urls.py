"""
Templates de URL para os endpoints do TSE 2026.
Gera as tarefas de coleta (URL → Redis stream) a partir de
combinações UF × cargo.
"""

# Mapeamento cargo → código TSE
CARGO_CODIGOS = {
    "presidente": "0001",
    "governador": "0003",
    "senador":    "0005",
}


def url_resultado(base: str, ele: str, uf: str, cargo: str) -> str:
    """
    URL de dados-simplificados (resultado variável por seção apurada).
    Exemplo: .../544/dados-simplificados/sp/sp-c0003-e000544-r.json
    """
    ele_padded = str(ele).zfill(6)
    return f"{base}/{ele}/dados-simplificados/{uf}/{uf}-c{cargo}-e{ele_padded}-r.json"


def url_fixos(base: str, ele: str, cargo: str) -> str:
    """
    URL de configuração fixa (metadados de candidatos).
    Exemplo: .../544/config/ele-c0003-e000544-cf.json
    """
    ele_padded = str(ele).zfill(6)
    return f"{base}/{ele}/config/ele-c{cargo}-e{ele_padded}-cf.json"


def gerar_tarefas(ele: str, ufs: list[str], cargos: list[str]) -> list[dict]:
    """
    Retorna lista de dicts com url e stream para cada par UF × cargo (zip).
    O stream Redis segue o padrão megatron:{uf}:{cargo_nome}.
    """
    tarefas = []
    for uf, cargo_nome in zip(ufs, cargos):
        codigo = CARGO_CODIGOS.get(cargo_nome, "0003")
        tarefas.append({
            "url": url_resultado(base="{base}", ele=ele, uf=uf, cargo=codigo),
            "stream": f"megatron:{uf}:{cargo_nome}",
            "uf": uf,
            "cargo": cargo_nome,
        })
    return tarefas
