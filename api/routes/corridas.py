"""
Quais corridas estao sendo coletadas de fato.

O frontend oferecia 11 UFs x 5 cargos = 55 combinacoes enquanto o backend
coletava 5. As outras 50 ficavam em "sem boletim" para sempre, sem explicar
por que — foi exatamente o que apareceu no primeiro print de SP + Deputado
Federal. Com este endpoint o seletor passa a listar so o que existe.

A fonte e a mesma do consumer (consumer.STREAMS), entao nao ha como a lista
divergir do que e realmente assinado.
"""
from fastapi import APIRouter

import consumer

router = APIRouter()

ROTULOS = {
    "presidente": "Presidente",
    "governador": "Governador",
    "senador": "Senador",
    "dep_federal": "Deputado Federal",
    "dep_estadual": "Deputado Estadual",
}

UF_NOMES = {
    "br": "Brasil", "ac": "Acre", "al": "Alagoas", "am": "Amazonas",
    "ap": "Amapá", "ba": "Bahia", "ce": "Ceará", "df": "Distrito Federal",
    "es": "Espírito Santo", "go": "Goiás", "ma": "Maranhão", "mg": "Minas Gerais",
    "ms": "Mato Grosso do Sul", "mt": "Mato Grosso", "pa": "Pará",
    "pb": "Paraíba", "pe": "Pernambuco", "pi": "Piauí", "pr": "Paraná",
    "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte", "ro": "Rondônia",
    "rr": "Roraima", "rs": "Rio Grande do Sul", "sc": "Santa Catarina",
    "se": "Sergipe", "sp": "São Paulo", "to": "Tocantins",
}


@router.get("/corridas")
async def get_corridas():
    """
    Corridas assinadas, com a marca de quais ja receberam boletim.

    `com_dado=false` significa "configurada mas ainda sem primeiro boletim" —
    normal no comeco da noite, e diferente de "nao existe".
    """
    itens = []
    for stream in sorted(consumer.STREAMS):
        _, uf, cargo = stream.split(":", 2)
        itens.append({
            "uf": uf,
            "uf_nome": UF_NOMES.get(uf, uf.upper()),
            "cargo": cargo,
            "cargo_nome": ROTULOS.get(cargo, cargo),
            "com_dado": consumer.get_last_snapshot(stream) is not None,
        })
    return {"total": len(itens), "corridas": itens}
