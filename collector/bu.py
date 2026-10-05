"""
Parser do BOLETIM DE URNA (bu.dat) do TSE — ASN.1 BER, sem a especificacao
oficial: a estrutura foi mapeada em 04/10/2026 sobre boletins reais do
pleito 3220 (ver tests/fixtures/*-bu.dat).

Envelope (SEQUENCE): cabecalho, fase, identificacao, tipo, conteudo (OCTET
STRING com o EntidadeBoletimUrna codificado).
EntidadeBoletimUrna (SEQUENCE), por posicao:
  [0] cabecalho {dataGeracao, idEleitoral}
  [1] fase
  [2] urna {tipo, versao, correspondencia, ...}
  [3] identificacaoSecao {municipioZona {municipio, zona}, local, secao}
  [4] dataHoraEmissao (GeneralString "AAAAMMDDTHHMMSS")
  [5] dadosSecao [0] {abertura, encerramento, ...}
  [6] qtdEleitoresLibCodigo
  [7] [1] {...} (biometria)
  [8] resultadosVotacaoPorEleicao SEQUENCE OF {
        idEleicao, qtdEleitoresAptos, ?, ?, resultadosVotacao SEQUENCE OF {
            tipoCargo (1 majoritario, 2 proporcional), qtdComparecimento,
            totaisVotosCargo SEQUENCE OF {
                codigoCargo [1] (1 presidente, 3 governador, 5 senador,
                                 6 dep. federal, 7 dep. estadual),
                ordemImpressao,
                votosVotaveis SEQUENCE OF {
                    [1] tipoVoto (1 nominal, 2 branco, 3 nulo, 4 legenda),
                    [2] quantidadeVotos,
                    [3] identificacaoVotavel {partido, codigo}  (so nominal/legenda),
                    ordem, assinatura }}}, assinaturas... }
  [9] {chaveAssinaturaVotosVotavel}
Validacao interna: para cada cargo, nominal + branco + nulo + legenda ==
qtdComparecimento x votos por eleitor (1; senador em 2026 = 2, duas vagas).
"""
from __future__ import annotations

from dataclasses import dataclass, field

CARGO = {1: "presidente", 3: "governador", 5: "senador", 6: "dep_federal", 7: "dep_estadual",
         2: "vice_presidente", 4: "vice_governador", 8: "dep_distrital", 9: "suplente1_senador",
         10: "suplente2_senador", 11: "prefeito", 12: "vice_prefeito", 13: "vereador"}
TIPO_VOTO = {1: "nominal", 2: "branco", 3: "nulo", 4: "legenda"}


# ------------------------------------------------------------- BER minimo

def _tlv(b: bytes, i: int):
    first = b[i]; cls = first >> 6; con = bool(first & 0x20); num = first & 0x1F; i += 1
    if num == 0x1F:
        num = 0
        while True:
            c = b[i]; i += 1; num = (num << 7) | (c & 0x7F)
            if not c & 0x80:
                break
    ln = b[i]; i += 1
    if ln & 0x80:
        n = ln & 0x7F; ln = int.from_bytes(b[i:i + n], "big"); i += n
    return cls, num, con, i, ln


def parse_ber(b: bytes, i: int = 0, fim: int | None = None) -> list[dict]:
    fim = len(b) if fim is None else fim
    nos = []
    while i < fim:
        cls, num, con, j, ln = _tlv(b, i)
        if con:
            nos.append({"cls": cls, "tag": num, "filhos": parse_ber(b, j, j + ln)})
        else:
            nos.append({"cls": cls, "tag": num, "val": b[j:j + ln]})
        i = j + ln
    return nos


def _int(no: dict) -> int:
    v = no.get("val", b"")
    return int.from_bytes(v, "big", signed=True) if v else 0


def _str(no: dict) -> str:
    return no.get("val", b"").decode("latin1")


# -------------------------------------------------------------- modelo

@dataclass
class Votavel:
    cargo: str
    tipo: str            # nominal | branco | nulo | legenda
    votos: int
    partido: int | None = None
    codigo: int | None = None      # numero de urna (nominal) ou do partido (legenda)
    ordem: int | None = None


@dataclass
class ResultadoCargo:
    eleicao: int
    cargo: str
    tipo_cargo: int      # 1 majoritario, 2 proporcional
    comparecimento: int
    votaveis: list[Votavel] = field(default_factory=list)

    def soma(self) -> int:
        return sum(v.votos for v in self.votaveis)

    @property
    def votos_por_eleitor(self) -> int:
        """1 na maioria dos cargos; 2 em senador quando ha duas vagas (2026)."""
        if self.comparecimento <= 0 or self.soma() % self.comparecimento:
            return 0
        return self.soma() // self.comparecimento

    def consistente(self) -> bool:
        return self.votos_por_eleitor in (1, 2)


@dataclass
class Boletim:
    municipio: int
    zona: int
    local: int
    secao: int
    emissao: str
    eleitores_lib_codigo: int
    aptos: dict[int, int]                 # idEleicao -> qtdEleitoresAptos
    resultados: list[ResultadoCargo]

    def consistente(self) -> bool:
        return all(r.consistente() for r in self.resultados)


def _conteudo(envelope: list[dict]) -> bytes:
    seq = envelope[0]["filhos"]
    octetos = [n for n in seq if "val" in n and n["cls"] == 0 and n["tag"] == 4]
    if not octetos:
        raise ValueError("envelope sem conteudo (OCTET STRING)")
    return max(octetos, key=lambda n: len(n["val"]))["val"]


def ler_boletim(raw: bytes) -> Boletim:
    bu = parse_ber(_conteudo(parse_ber(raw)))[0]["filhos"]
    ident = bu[3]["filhos"]
    mz = ident[0]["filhos"]
    municipio, zona = _int(mz[0]), _int(mz[1])
    local, secao = _int(ident[1]), _int(ident[2])
    emissao = _str(bu[4])
    lib_codigo = _int(bu[6]) if "val" in bu[6] else 0

    aptos: dict[int, int] = {}
    resultados: list[ResultadoCargo] = []
    for ele in bu[8]["filhos"]:
        f = ele["filhos"]
        id_ele = _int(f[0])
        aptos[id_ele] = _int(f[1])
        # resultadosVotacao e a primeira SEQUENCE (construida, classe universal) apos os inteiros
        rvs = next(x for x in f if "filhos" in x and x["cls"] == 0)
        for rv in rvs["filhos"]:
            g = rv["filhos"]
            tipo_cargo, comparecimento = _int(g[0]), _int(g[1])
            for tvc in g[2]["filhos"]:
                h = tvc["filhos"]
                cod_cargo = _int(h[0])
                rc = ResultadoCargo(id_ele, CARGO.get(cod_cargo, f"cargo_{cod_cargo}"), tipo_cargo, comparecimento)
                for vot in h[2]["filhos"]:
                    k = vot["filhos"]
                    tipo = _int(k[0]); qtd = _int(k[1])
                    partido = codigo = None
                    ordem = None
                    for extra in k[2:]:
                        if "filhos" in extra and extra["cls"] == 2 and extra["tag"] == 3:
                            partido, codigo = _int(extra["filhos"][0]), _int(extra["filhos"][1])
                        elif "val" in extra and extra["cls"] == 0 and extra["tag"] == 2:
                            ordem = _int(extra)
                    rc.votaveis.append(Votavel(rc.cargo, TIPO_VOTO.get(tipo, f"tipo_{tipo}"), qtd, partido, codigo, ordem))
                resultados.append(rc)
    return Boletim(municipio, zona, local, secao, emissao, lib_codigo, aptos, resultados)
