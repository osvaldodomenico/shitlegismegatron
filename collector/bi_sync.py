"""
Sincronizador MEGATRON -> Legis Inteligencia (BI, MySQL `shiftBI`).

Grava a eleicao de 2026 (SP + presidente) nas MESMAS tabelas e no MESMO formato
que o BI ja usa para 2014-2024 (padrao Base dos Dados: categorias em minusculas
sem acento, proporcoes em %, ids como texto). Assim mapa, rankings, adversarios
e partido passam a funcionar para 2026 sem mudar codigo do BI.

Fontes:
  - Postgres do MEGATRON: urna_bu/urna_votos (secao), votos_municipio (cidade,
    zona, UF, BR), locais_votacao (cadastro TSE de locais), municipios (IBGE).
  - Dados abertos do TSE 2026 (cdn.tse.jus.br/estatistica/sead/odsele): candidatos,
    bens, perfil do eleitorado e prestacao de contas — rebaixados quando o
    Last-Modified muda.

Idempotente e retomavel: o que ja foi enviado fica em tabelas bi_sync_* no
Postgres do MEGATRON, com a assinatura (hash do BU, hg/pst do boletim, ou
Last-Modified do arquivo). Mudou a assinatura -> apaga as linhas daquela chave
no BI (sempre filtrando ano=2026) e reinsere.

NUNCA toca em linha de outro ano: todo DELETE leva `ano = 2026`.
Ao terminar uma rodada com escrita, marca megatron:bi:agg_pendente no Redis;
o cron do host (scripts/bi_agg.sh) roda o pipeline de agregacao do BI.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import sys
import time
import unicodedata
import zipfile
from datetime import date, datetime
from pathlib import Path

import asyncpg
import httpx
import pymysql
import redis.asyncio as aioredis

POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "")
BI = dict(host=os.environ.get("BI_DB_HOST", "shiftworks_mysql_shiftbi"), port=int(os.environ.get("BI_DB_PORT", "3306")),
          user=os.environ.get("BI_DB_USER", "root"), password=os.environ.get("BI_DB_PASS", ""),
          database=os.environ.get("BI_DB_NAME", "shiftBI"), charset="utf8mb4", autocommit=False)
UF = os.environ.get("BI_UF", "sp").lower()
ANO = 2026
DATA = "2026-10-04"
TIPO = "eleicao ordinaria"
TURNO = 1
DIR_TSE = Path(os.environ.get("BI_DIR_TSE", "/dados/tse"))
CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
INTERVALO = int(os.environ.get("BI_INTERVAL_SECONDS", "900"))
LOTE = int(os.environ.get("BI_LOTE", "3000"))
SECOES_POR_LOTE = int(os.environ.get("BI_SECOES_POR_LOTE", "100"))
ETAPAS = [e.strip() for e in os.environ.get(
    "BI_ETAPAS", "locais,candidatos,bens,lugares,perfil,receitas,despesas,secoes").split(",") if e.strip()]
HEARTBEAT = "megatron:heartbeat:bi_sync"
_REDIS = None   # definido no main; usado para renovar o batimento dentro das etapas longas


async def batimento(**extra) -> None:
    if _REDIS is not None:
        try:
            await _REDIS.set(HEARTBEAT, json.dumps({"ts": time.time(), **extra}), ex=INTERVALO * 4)
        except Exception:  # noqa: BLE001
            pass
AGG_PENDENTE = "megatron:bi:agg_pendente"

CARGO_BI = {"presidente": "presidente", "governador": "governador", "senador": "senador",
            "dep_federal": "deputado federal", "dep_estadual": "deputado estadual"}
ELE = {"presidente": "6257"}          # demais cargos: 6259

NULOS = {"#NULO", "#NULO#", "#NE", "NÃO DIVULGÁVEL", "NAO DIVULGAVEL", "-1", "-3", "-4", ""}


# ---------------------------------------------------------------- formato

def norm(s) -> str | None:
    """Categoria no padrao do BI: minusculas, sem acento. #NULO etc -> None."""
    if s is None:
        return None
    s = str(s).strip()
    if s.upper() in NULOS:
        return None
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("º", "o").replace("ª", "a")
    return s.lower()


def bruto(s) -> str | None:
    if s is None:
        return None
    s = str(s).strip()
    return None if s.upper() in NULOS else s


def titulo(s) -> str | None:
    s = bruto(s)
    return s.title() if s else None


def data_br(s) -> str | None:
    s = bruto(s)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def num_br(s) -> float | None:
    s = bruto(s)
    if s is None:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def inteiro(v) -> int:
    try:
        return int(str(v or "0").replace(".", "").strip() or 0)
    except ValueError:
        return 0


def pct(a, b) -> float:
    return round(100.0 * a / b, 6) if b else 0.0


def ele_de(cargo: str) -> str:
    return ELE.get(cargo, "6259")


def idade_em(nasc: str | None) -> int | None:
    if not nasc:
        return None
    n = date.fromisoformat(nasc)
    e = date(2026, 10, 4)
    return e.year - n.year - ((e.month, e.day) < (n.month, n.day))


# ---------------------------------------------------------------- BI (MySQL)

def bi_conectar():
    return pymysql.connect(**BI)


def bi_inserir(con, tabela: str, colunas: list[str], linhas: list[tuple]) -> int:
    if not linhas:
        return 0
    sql = f"INSERT INTO {tabela} ({','.join(colunas)}) VALUES ({','.join(['%s'] * len(colunas))})"
    with con.cursor() as cur:
        for i in range(0, len(linhas), LOTE):
            cur.executemany(sql, linhas[i:i + LOTE])
    return len(linhas)


def bi_inserir_fluxo(con, tabela: str, colunas: list[str], gerador, bloco: int = 20000) -> int:
    """Insere de um gerador em blocos, sem acumular o arquivo inteiro na memoria."""
    total, buf = 0, []
    for linha in gerador:
        buf.append(linha)
        if len(buf) >= bloco:
            total += bi_inserir(con, tabela, colunas, buf); buf = []
    return total + bi_inserir(con, tabela, colunas, buf)


def bi_apagar(con, sql: str, args: tuple) -> int:
    assert "ano = 2026" in sql or "ano=2026" in sql, "todo DELETE no BI precisa filtrar ano = 2026"
    with con.cursor() as cur:
        return cur.execute(sql, args)


# ---------------------------------------------------------------- estado (Postgres MEGATRON)

DDL = """
CREATE TABLE IF NOT EXISTS bi_sync_chave (
    chave       TEXT PRIMARY KEY,           -- ex.: arquivo:candidatos, lugar:municipio:dep_federal:71072:
    assinatura  TEXT,
    linhas      BIGINT,
    enviado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS bi_sync_secao (
    cod_mun TEXT NOT NULL, zona INT NOT NULL, secao INT NOT NULL,
    hash TEXT, linhas INT, enviado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cod_mun, zona, secao)
);
"""


async def estado(pg, chave: str) -> str | None:
    return await pg.fetchval("SELECT assinatura FROM bi_sync_chave WHERE chave=$1", chave)


async def marcar(pg, chave: str, assinatura: str, linhas: int) -> None:
    await pg.execute(
        "INSERT INTO bi_sync_chave (chave, assinatura, linhas, enviado_em) VALUES ($1,$2,$3,NOW()) "
        "ON CONFLICT (chave) DO UPDATE SET assinatura=EXCLUDED.assinatura, linhas=EXCLUDED.linhas, enviado_em=NOW()",
        chave, assinatura, linhas)


async def mapa_ibge(pg) -> dict[str, str]:
    rows = await pg.fetch("SELECT cod_tse, cod_ibge FROM municipios WHERE uf=$1", UF)
    return {r["cod_tse"]: r["cod_ibge"] for r in rows}


# ---------------------------------------------------------------- arquivos TSE

async def arquivo_tse(client: httpx.AsyncClient, caminho: str) -> tuple[Path, str]:
    """Baixa se o Last-Modified mudou. Devolve (zip local, assinatura)."""
    url = f"{CDN}/{caminho}"
    destino = DIR_TSE / Path(caminho).name
    h = await client.head(url, timeout=60)
    h.raise_for_status()
    assinatura = f"{h.headers.get('last-modified')}|{h.headers.get('content-length')}"
    marca = destino.with_suffix(destino.suffix + ".assinatura")
    if not destino.exists() or not marca.exists() or marca.read_text() != assinatura:
        tmp = destino.with_suffix(destino.suffix + ".part")
        async with client.stream("GET", url, timeout=1800) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                async for bloco in r.aiter_bytes(1 << 20):
                    f.write(bloco)
        tmp.replace(destino)
        marca.write_text(assinatura)
    return destino, assinatura


def ler_csv(zip_path: Path, nome: str):
    with zipfile.ZipFile(zip_path) as z:
        with z.open(nome) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin1"), delimiter=";", quotechar='"')


def nomes_no_zip(zip_path: Path, sufixos: list[str], prefixo: str) -> list[str]:
    with zipfile.ZipFile(zip_path) as z:
        return [n for n in z.namelist() if n.startswith(prefixo) and any(n.endswith(s) for s in sufixos)]


# ---------------------------------------------------------------- etapas

async def etapa_locais(pg, con, ibge) -> int:
    """locais_votacao (cadastro TSE 2026) -> novo_perfil_eleitorado_local_votacao + local_secao."""
    assinatura = str(await pg.fetchval("SELECT max(dt_geracao||' '||hh_geracao)||'|'||count(*) FROM locais_votacao WHERE upper(sg_uf)=upper($1)", UF))
    if await estado(pg, "locais") == assinatura:
        return 0
    rows = await pg.fetch("""
        SELECT cd_municipio, nr_zona, nr_secao, cd_tipo_secao_agregada, nr_local_votacao, nm_local_votacao, ds_tipo_local,
               ds_endereco, nm_bairro, nr_cep, nr_telefone_local, nr_latitude, nr_longitude, ds_situ_local_votacao,
               ds_situ_zona, ds_situ_secao, ds_situ_localidade, ds_situ_secao_acessibilidade, qt_eleitor_secao
        FROM locais_votacao WHERE upper(sg_uf)=upper($1)""", UF)
    sg = UF.upper()
    novo, local = [], []
    for r in rows:
        lat, lon = num_br(r["nr_latitude"]), num_br(r["nr_longitude"])
        lat = None if lat in (None, -1.0) else lat
        lon = None if lon in (None, -1.0) else lon
        novo.append((ANO, TURNO, sg, ibge.get(r["cd_municipio"]), r["cd_municipio"], r["nr_zona"], r["nr_secao"],
                     r["cd_tipo_secao_agregada"], r["nr_local_votacao"], bruto(r["nm_local_votacao"]), norm(r["ds_tipo_local"]),
                     bruto(r["ds_endereco"]), bruto(r["nm_bairro"]), bruto(r["nr_cep"]), bruto(r["nr_telefone_local"]),
                     lat, lon, norm(r["ds_situ_local_votacao"]), norm(r["ds_situ_zona"]), norm(r["ds_situ_secao"]),
                     norm(r["ds_situ_localidade"]), norm(r["ds_situ_secao_acessibilidade"]), r["qt_eleitor_secao"], None))
        if lat is not None and lon is not None:
            p = f"POINT({lon} {lat})"
            local.append((sg, ibge.get(r["cd_municipio"]), r["nr_zona"], r["nr_secao"], ANO, p, p, p, p, None))
    bi_apagar(con, "DELETE FROM novo_perfil_eleitorado_local_votacao WHERE ano = 2026 AND sigla_uf = %s", (sg,))
    bi_apagar(con, "DELETE FROM local_secao WHERE ano = 2026 AND sigla_uf = %s", (sg,))
    n = bi_inserir(con, "novo_perfil_eleitorado_local_votacao",
                   ["ano", "turno", "sigla_uf", "id_municipio", "id_municipio_tse", "zona", "secao", "tipo_secao_agregada",
                    "numero", "nome", "tipo", "endereco", "bairro", "cep", "telefone", "latitude", "longitude", "situacao",
                    "situacao_zona", "situacao_secao", "situacao_localidade", "situacao_secao_acessibilidade",
                    "eleitores_secao", "etl_id"], novo)
    n += bi_inserir(con, "local_secao", ["sigla_uf", "id_municipio", "zona", "secao", "ano", "melhor_urbano", "melhor_rural",
                                         "tse_recente", "tse_distribuido", "etl_id"], local)
    con.commit()
    await marcar(pg, "locais", assinatura, n)
    return n


async def etapa_candidatos(pg, con, client) -> int:
    z, assinatura = await arquivo_tse(client, "consulta_cand/consulta_cand_2026.zip")
    if await estado(pg, "arquivo:candidatos") == assinatura:
        return 0
    linhas = []
    for nome in (f"consulta_cand_2026_{UF.upper()}.csv", "consulta_cand_2026_BR.csv"):
        for r in ler_csv(z, nome):
            nasc = data_br(r["DT_NASCIMENTO"])
            linhas.append((ANO, r["CD_ELEICAO"], TIPO, DATA, r["SG_UF"], None, None,
                           bruto(r["NR_TITULO_ELEITORAL_CANDIDATO"]), bruto(r["NR_CPF_CANDIDATO"]), r["SQ_CANDIDATO"],
                           r["NR_CANDIDATO"], titulo(r["NM_CANDIDATO"]), titulo(r["NM_URNA_CANDIDATO"]), r["NR_PARTIDO"],
                           bruto(r["SG_PARTIDO"]), norm(r["DS_CARGO"]), norm(r["DS_SITUACAO_CANDIDATURA"]), nasc,
                           idade_em(nasc), norm(r["DS_GENERO"]), norm(r["DS_GRAU_INSTRUCAO"]), norm(r["DS_OCUPACAO"]),
                           norm(r["DS_ESTADO_CIVIL"]), "brasileira", bruto(r["SG_UF_NASCIMENTO"]), None,
                           None if norm(r["DS_EMAIL"]) is None else r["DS_EMAIL"].lower(), norm(r["DS_COR_RACA"]), None))
    bi_apagar(con, "DELETE FROM candidatos WHERE ano = 2026 AND sigla_uf IN (%s, 'BR')", (UF.upper(),))
    n = bi_inserir(con, "candidatos",
                   ["ano", "id_eleicao", "tipo_eleicao", "data_eleicao", "sigla_uf", "id_municipio", "id_municipio_tse",
                    "titulo_eleitoral", "cpf", "sequencial", "numero", "nome", "nome_urna", "numero_partido",
                    "sigla_partido", "cargo", "situacao", "data_nascimento", "idade", "genero", "instrucao", "ocupacao",
                    "estado_civil", "nacionalidade", "sigla_uf_nascimento", "municipio_nascimento", "email", "raca",
                    "etl_id"], linhas)
    con.commit()
    await marcar(pg, "arquivo:candidatos", assinatura, n)
    # situacao final por candidato (DS_SIT_TOT_TURNO), para o campo `resultado`
    sit = {}
    for nome in (f"consulta_cand_2026_{UF.upper()}.csv", "consulta_cand_2026_BR.csv"):
        for r in ler_csv(z, nome):
            if norm(r["DS_SIT_TOT_TURNO"]):
                sit[r["SQ_CANDIDATO"]] = norm(r["DS_SIT_TOT_TURNO"])
    await pg.execute("INSERT INTO bi_sync_chave (chave, assinatura, linhas) VALUES ('situacao_tse',$1,$2) "
                     "ON CONFLICT (chave) DO UPDATE SET assinatura=EXCLUDED.assinatura, linhas=EXCLUDED.linhas, enviado_em=NOW()",
                     json.dumps(sit), len(sit))
    return n


async def etapa_bens(pg, con, client) -> int:
    z, assinatura = await arquivo_tse(client, "bem_candidato/bem_candidato_2026.zip")
    if await estado(pg, "arquivo:bens") == assinatura:
        return 0
    titulos = {}
    zc = DIR_TSE / "consulta_cand_2026.zip"
    for nome in (f"consulta_cand_2026_{UF.upper()}.csv", "consulta_cand_2026_BR.csv"):
        for r in ler_csv(zc, nome):
            titulos[r["SQ_CANDIDATO"]] = bruto(r["NR_TITULO_ELEITORAL_CANDIDATO"])
    linhas = []
    for nome in (f"bem_candidato_2026_{UF.upper()}.csv", "bem_candidato_2026_BR.csv"):
        for r in ler_csv(z, nome):
            linhas.append((ANO, r["SG_UF"], r["CD_ELEICAO"], TIPO, DATA, titulos.get(r["SQ_CANDIDATO"]), r["SQ_CANDIDATO"],
                           bruto(r["DS_TIPO_BEM_CANDIDATO"]), bruto(r["DS_BEM_CANDIDATO"]), num_br(r["VR_BEM_CANDIDATO"]), None))
    bi_apagar(con, "DELETE FROM bens_candidato WHERE ano = 2026 AND sigla_uf IN (%s, 'BR')", (UF.upper(),))
    n = bi_inserir(con, "bens_candidato", ["ano", "sigla_uf", "id_eleicao", "tipo_eleicao", "data_eleicao",
                                           "titulo_eleitoral_candidato", "sequencial_candidato", "tipo_item",
                                           "descricao_item", "valor_item", "etl_id"], linhas)
    con.commit()
    await marcar(pg, "arquivo:bens", assinatura, n)
    return n


async def etapa_perfil(pg, con, client, ibge) -> int:
    """perfil_eleitorado_2026 (SP) -> perfil_eleitorado_municipio_zona, com os CODIGOS do TSE (padrao do BI)."""
    z, assinatura = await arquivo_tse(client, "perfil_eleitorado/perfil_eleitorado_2026.zip")
    if await estado(pg, "arquivo:perfil") == assinatura:
        return 0
    sg = UF.upper()

    def linhas():
        for r in ler_csv(z, f"perfil_eleitorado_2026_{UF.upper()}.csv"):
            yield (ANO, sg, ibge.get(r["CD_MUNICIPIO"]), r["CD_MUNICIPIO"], None, inteiro(r["NR_ZONA"]),
                   inteiro(r["CD_GENERO"]), inteiro(r["CD_ESTADO_CIVIL"]), inteiro(r["CD_FAIXA_ETARIA"]),
                   inteiro(r["CD_GRAU_ESCOLARIDADE"]), inteiro(r["QT_ELEITORES"]), inteiro(r["QT_ELEITORES_BIOMETRIA"]),
                   inteiro(r["QT_ELEITORES_DEFICIENCIA"]), None)
    bi_apagar(con, "DELETE FROM perfil_eleitorado_municipio_zona WHERE ano = 2026 AND sigla_uf = %s", (sg,))
    n = bi_inserir_fluxo(con, "perfil_eleitorado_municipio_zona",
                   ["ano", "sigla_uf", "id_municipio", "id_municipio_tse", "situacao_biometria", "zona", "genero",
                    "estado_civil", "grupo_idade", "instrucao", "eleitores", "eleitores_biometria",
                    "eleitores_deficiencia", "etl_id"], linhas())
    con.commit()
    await marcar(pg, "arquivo:perfil", assinatura, n)
    return n


def _fin_comum(r):
    return (ANO, TURNO, r["CD_ELEICAO"], TIPO, DATA, r["SG_UF"], None, None, None, r["SQ_CANDIDATO"], r["NR_CANDIDATO"],
            bruto(r["NR_CNPJ_PRESTADOR_CONTA"]), r["NR_PARTIDO"], bruto(r["SG_PARTIDO"]), norm(r["DS_CARGO"]))


FIN_COMUM = ["ano", "turno", "id_eleicao", "tipo_eleicao", "data_eleicao", "sigla_uf", "id_municipio", "id_municipio_tse",
             "titulo_eleitoral_candidato", "sequencial_candidato", "numero_candidato", "cnpj_candidato", "numero_partido",
             "sigla_partido", "cargo"]


async def etapa_receitas(pg, con, client) -> int:
    z, assinatura = await arquivo_tse(client, "prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip")
    if await estado(pg, "arquivo:receitas") == assinatura:
        return 0
    def linhas():
      for nome in (f"receitas_candidatos_2026_{UF.upper()}.csv", "receitas_candidatos_2026_BR.csv"):
        for r in ler_csv(z, nome):
            yield (_fin_comum(r) + (
                bruto(r["SQ_RECEITA"]), data_br(r["DT_RECEITA"]), norm(r["DS_FONTE_RECEITA"]), norm(r["DS_ORIGEM_RECEITA"]),
                norm(r["DS_NATUREZA_RECEITA"]), norm(r["DS_ESPECIE_RECEITA"]), None, bruto(r["DS_RECEITA"]),
                num_br(r["VR_RECEITA"]), bruto(r["SQ_CANDIDATO_DOADOR"]), bruto(r["NR_CPF_CNPJ_DOADOR"]),
                bruto(r["SG_UF_DOADOR"]), bruto(r["CD_MUNICIPIO_DOADOR"]), bruto(r["NM_DOADOR"]), bruto(r["NM_DOADOR_RFB"]),
                norm(r["DS_CARGO_CANDIDATO_DOADOR"]), bruto(r["NR_PARTIDO_DOADOR"]), bruto(r["SG_PARTIDO_DOADOR"]),
                norm(r["DS_ESFERA_PARTIDARIA_DOADOR"]), bruto(r["NR_CANDIDATO_DOADOR"]), bruto(r["CD_CNAE_DOADOR"]),
                bruto(r["DS_CNAE_DOADOR"]), bruto(r["NR_RECIBO_DOACAO"]), bruto(r["NR_DOCUMENTO_DOACAO"]),
                norm(r["TP_PRESTACAO_CONTAS"]), data_br(r["DT_PRESTACAO_CONTAS"]), bruto(r["SQ_PRESTADOR_CONTAS"]),
                bruto(r["NR_CNPJ_PRESTADOR_CONTA"]), None))
    bi_apagar(con, "DELETE FROM receitas_candidato WHERE ano = 2026 AND sigla_uf IN (%s, 'BR')", (UF.upper(),))
    n = bi_inserir_fluxo(con, "receitas_candidato", FIN_COMUM + [
        "sequencial_receita", "data_receita", "fonte_receita", "origem_receita", "natureza_receita", "especie_receita",
        "situacao_receita", "descricao_receita", "valor_receita", "sequencial_candidato_doador", "cpf_cnpj_doador",
        "sigla_uf_doador", "id_municipio_tse_doador", "nome_doador", "nome_doador_rf", "cargo_candidato_doador",
        "numero_partido_doador", "sigla_partido_doador", "esfera_partidaria_doador", "numero_candidato_doador",
        "cnae_2_doador", "descricao_cnae_2_doador", "numero_recibo_doacao", "numero_documento_doacao",
        "tipo_prestacao_contas", "data_prestacao_contas", "sequencial_prestador_contas", "cnpj_prestador_contas",
        "etl_id"], linhas())
    con.commit()
    await marcar(pg, "arquivo:receitas", assinatura, n)
    return n


async def etapa_despesas(pg, con, client) -> int:
    z, assinatura = await arquivo_tse(client, "prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip")
    if await estado(pg, "arquivo:despesas") == assinatura:
        return 0
    def linhas():
      for nome in (f"despesas_contratadas_candidatos_2026_{UF.upper()}.csv", "despesas_contratadas_candidatos_2026_BR.csv"):
        for r in ler_csv(z, nome):
            yield (_fin_comum(r) + (
                bruto(r["SQ_DESPESA"]), data_br(r["DT_DESPESA"]), norm(r["DS_ORIGEM_DESPESA"]), bruto(r["DS_DESPESA"]),
                norm(r["DS_ORIGEM_DESPESA"]), num_br(r["VR_DESPESA_CONTRATADA"]), norm(r["TP_PRESTACAO_CONTAS"]),
                data_br(r["DT_PRESTACAO_CONTAS"]), bruto(r["SQ_PRESTADOR_CONTAS"]), bruto(r["NR_CNPJ_PRESTADOR_CONTA"]),
                norm(r["DS_TIPO_DOCUMENTO"]), bruto(r["NR_DOCUMENTO"]), bruto(r["NR_CPF_CNPJ_FORNECEDOR"]),
                bruto(r["NM_FORNECEDOR"]), bruto(r["NM_FORNECEDOR_RFB"]), bruto(r["CD_CNAE_FORNECEDOR"]),
                bruto(r["DS_CNAE_FORNECEDOR"]), norm(r["DS_TIPO_FORNECEDOR"]), norm(r["DS_ESFERA_PART_FORNECEDOR"]),
                bruto(r["SG_UF_FORNECEDOR"]), bruto(r["CD_MUNICIPIO_FORNECEDOR"]), bruto(r["SQ_CANDIDATO_FORNECEDOR"]),
                bruto(r["NR_CANDIDATO_FORNECEDOR"]), bruto(r["NR_PARTIDO_FORNECEDOR"]), bruto(r["SG_PARTIDO_FORNECEDOR"]),
                norm(r["DS_CARGO_FORNECEDOR"]), None))
    bi_apagar(con, "DELETE FROM despesas_candidato WHERE ano = 2026 AND sigla_uf IN (%s, 'BR')", (UF.upper(),))
    n = bi_inserir_fluxo(con, "despesas_candidato", FIN_COMUM + [
        "sequencial_despesa", "data_despesa", "tipo_despesa", "descricao_despesa", "origem_despesa", "valor_despesa",
        "tipo_prestacao_contas", "data_prestacao_contas", "sequencial_prestador_contas", "cnpj_prestador_contas",
        "tipo_documento", "numero_documento", "cpf_cnpj_fornecedor", "nome_fornecedor", "nome_fornecedor_rf",
        "cnae_2_fornecedor", "descricao_cnae_2_fornecedor", "tipo_fornecedor", "esfera_partidaria_fornecedor",
        "sigla_uf_fornecedor", "id_municipio_tse_fornecedor", "sequencial_candidato_fornecedor",
        "numero_candidato_fornecedor", "numero_partido_fornecedor", "sigla_partido_fornecedor", "cargo_fornecedor",
        "etl_id"], linhas())
    con.commit()
    await marcar(pg, "arquivo:despesas", assinatura, n)
    return n


# ---- cidade / zona (votos_municipio)

COLS_RCM = ["ano", "turno", "id_eleicao", "tipo_eleicao", "data_eleicao", "sigla_uf", "id_municipio", "id_municipio_tse"]
COLS_DET = ["aptos", "secoes", "secoes_agregadas", "aptos_totalizadas", "secoes_totalizadas", "comparecimento",
            "abstencoes", "votos_validos", "votos_brancos", "votos_nulos", "votos_nominais", "votos_legenda",
            "proporcao_comparecimento", "proporcao_votos_validos", "proporcao_votos_brancos", "proporcao_votos_nulos", "etl_id"]


async def etapa_lugares(pg, con, ibge) -> int:
    situacao = json.loads(await estado(pg, "situacao_tse") or "{}")
    agreg = {(r["m"], r["z"]): r["n"] for r in await pg.fetch(
        "SELECT cd_municipio m, nr_zona::text z, count(*) n FROM locais_votacao WHERE upper(sg_uf)=upper($1) AND cd_tipo_secao_agregada=2 GROUP BY 1,2", UF)}
    agreg_mun: dict[str, int] = {}
    for (m, _z), n in agreg.items():
        agreg_mun[m] = agreg_mun.get(m, 0) + n
    lugares = await pg.fetch("""
        SELECT nivel, cargo, cod_tse, cod_zona, hg, pst::text pst, etag
        FROM votos_municipio WHERE uf=$1 AND nivel IN ('municipio','zona')""", UF)
    total = 0
    sg = UF.upper()
    for l in lugares:
        if l["cargo"] not in CARGO_BI:
            continue
        chave = f"lugar:{l['nivel']}:{l['cargo']}:{l['cod_tse']}:{l['cod_zona']}"
        assinatura = f"{l['etag']}|{l['hg']}|{l['pst']}|{len(situacao)}"
        if await estado(pg, chave) == assinatura:
            continue
        p = json.loads(await pg.fetchval(
            "SELECT payload::text FROM votos_municipio WHERE uf=$1 AND cargo=$2 AND cod_tse=$3 AND cod_zona=$4",
            UF, l["cargo"], l["cod_tse"], l["cod_zona"]))
        cargo, mun, zona = CARGO_BI[l["cargo"]], l["cod_tse"], l["cod_zona"]
        z = [str(int(zona))] if zona else []
        base = (ANO, TURNO, ele_de(l["cargo"]), TIPO, DATA, sg, ibge.get(mun), mun, *z)
        cand = [base + (cargo, c.get("ccd"), c.get("cc"), "", c.get("sqcand"), c.get("n"),
                        situacao.get(str(c.get("sqcand")), "") or norm(c.get("st")) or "", inteiro(c.get("vap")), None)
                for c in p.get("cand") or [] if str(c.get("dvt", "Válido")).startswith("Válido")]
        partidos = p.get("partidos") or []
        part = [base + (cargo, x.get("n"), x.get("sg"), inteiro(x.get("tvtn")), inteiro(x.get("tvtl")), None) for x in partidos]
        t = p.get("totais") or {}
        e, s, v = t.get("e") or {}, t.get("s") or {}, t.get("v") or {}
        aptos, comp = inteiro(e.get("te")), inteiro(e.get("c"))
        vv, vb, vn = inteiro(v.get("vv")), inteiro(v.get("vb")), inteiro(v.get("tvn"))
        leg = sum(inteiro(x.get("tvtl")) for x in partidos)
        tot = vv + vb + vn
        det = [base + (cargo, aptos, inteiro(s.get("ts")), agreg.get((mun, z[0])) if z else agreg_mun.get(mun, 0),
                       inteiro(e.get("est")), inteiro(s.get("st")), comp, inteiro(e.get("a")), vv, vb, vn,
                       inteiro(v.get("vnom")), leg, pct(comp, aptos), pct(vv, tot), pct(vb, tot), pct(vn, tot), None)]
        suf = "_zona" if zona else ""
        filtro = "ano = 2026 AND sigla_uf = %s AND cargo = %s AND id_municipio_tse = %s" + (" AND zona = %s" if zona else "")
        args = (sg, cargo, mun, *z)
        cz = COLS_RCM + (["zona"] if zona else [])
        bi_apagar(con, f"DELETE FROM resultados_candidato_municipio{suf} WHERE {filtro}", args)
        bi_apagar(con, f"DELETE FROM resultados_partido_municipio{suf} WHERE {filtro}", args)
        bi_apagar(con, f"DELETE FROM detalhes_votacao_municipio{suf} WHERE {filtro}", args)
        n = bi_inserir(con, f"resultados_candidato_municipio{suf}", cz + ["cargo", "numero_partido", "sigla_partido",
                       "titulo_eleitoral_candidato", "sequencial_candidato", "numero_candidato", "resultado", "votos", "etl_id"], cand)
        n += bi_inserir(con, f"resultados_partido_municipio{suf}", cz + ["cargo", "numero_partido", "sigla_partido",
                        "votos_nominais", "votos_legenda", "etl_id"], part)
        n += bi_inserir(con, f"detalhes_votacao_municipio{suf}", cz + ["cargo"] + COLS_DET, det)
        con.commit()
        await marcar(pg, chave, assinatura, n)
        total += n
        await batimento(etapa="lugares", linhas=total)
    return total


# ---- secao (boletins de urna)

async def mapa_candidatos(pg) -> dict[tuple[str, int], dict]:
    """(cargo, numero) -> {sqcand, partido, sigla}: da lista do TSE (UF para estaduais, BR para presidente)."""
    m = {}
    rows = await pg.fetch("""
        SELECT cargo, payload::text p FROM votos_municipio
        WHERE (nivel='uf' AND uf=$1 AND cargo<>'presidente') OR (nivel='br' AND cargo='presidente')""", UF)
    for r in rows:
        for c in json.loads(r["p"]).get("cand") or []:
            m[(r["cargo"], inteiro(c.get("n")))] = {"sq": c.get("sqcand"), "partido": c.get("ccd"), "sigla": c.get("cc")}
    return m


async def mapa_partidos(pg) -> dict[str, str]:
    m = {}
    for r in await pg.fetch("SELECT payload::text p FROM votos_municipio WHERE (nivel='uf' AND uf=$1) OR nivel='br'", UF):
        for x in json.loads(r["p"]).get("partidos") or []:
            m[str(x.get("n"))] = x.get("sg")
    return m


async def etapa_secoes(pg, con, ibge) -> int:
    cands = await mapa_candidatos(pg)
    siglas = await mapa_partidos(pg)
    inv = {v: k for k, v in CARGO_BI.items()}
    sg = UF.upper()
    total = 0
    while True:
        pend = await pg.fetch("""
            SELECT b.cod_mun, b.zona, b.secao, b.hash, b.aptos::text aptos, b.detalhe::text detalhe, s.hash enviado
            FROM urna_bu b LEFT JOIN bi_sync_secao s USING (cod_mun, zona, secao)
            WHERE b.uf=$1 AND (s.hash IS NULL OR s.hash <> b.hash)
            ORDER BY b.cod_mun, b.zona, b.secao LIMIT $2""", UF, SECOES_POR_LOTE)
        if not pend:
            return total
        chaves = [(p["cod_mun"], p["zona"], p["secao"]) for p in pend]
        votos = await pg.fetch("""
            SELECT cod_mun, zona, secao, eleicao, cargo, tipo, partido, codigo, votos FROM urna_votos
            WHERE uf=$1 AND (cod_mun, zona, secao) IN (SELECT * FROM unnest($2::text[], $3::int[], $4::int[]))""",
            UF, [c[0] for c in chaves], [c[1] for c in chaves], [c[2] for c in chaves])
        por_secao: dict[tuple, list] = {}
        for v in votos:
            por_secao.setdefault((v["cod_mun"], v["zona"], v["secao"]), []).append(v)
        rcs, rps, dvs = [], [], []
        for p in pend:
            k = (p["cod_mun"], p["zona"], p["secao"])
            mun, zona, secao = k
            aptos = json.loads(p["aptos"] or "{}")
            detalhe = json.loads(p["detalhe"] or "{}")
            agg: dict[str, dict] = {}
            for v in por_secao.get(k, []):
                c = v["cargo"]
                if c not in CARGO_BI:
                    continue
                a = agg.setdefault(c, {"ele": str(v["eleicao"]), "nom": 0, "fora": 0, "branco": 0, "nulo": 0, "leg": 0, "part": {}})
                if v["tipo"] == "nominal":
                    info = cands.get((c, v["codigo"]))
                    if info is None:
                        a["fora"] += v["votos"]          # numero sem candidato: o TSE conta como nulo
                        continue
                    a["nom"] += v["votos"]
                    pp = a["part"].setdefault(str(info["partido"]), [0, 0])
                    pp[0] += v["votos"]
                    rcs.append((ANO, TURNO, str(v["eleicao"]), TIPO, DATA, sg, ibge.get(mun), mun, str(zona), str(secao),
                                CARGO_BI[c], info["partido"], info["sigla"], "", info["sq"], str(v["codigo"]), v["votos"]))
                elif v["tipo"] == "legenda":
                    a["leg"] += v["votos"]
                    pp = a["part"].setdefault(str(v["partido"]), [0, 0])
                    pp[1] += v["votos"]
                elif v["tipo"] == "branco":
                    a["branco"] += v["votos"]
                elif v["tipo"] == "nulo":
                    a["nulo"] += v["votos"]
            for c, a in agg.items():
                for npart, (nom, leg) in a["part"].items():
                    rps.append((ANO, TURNO, a["ele"], TIPO, DATA, sg, ibge.get(mun), mun, str(zona), str(secao), CARGO_BI[c],
                                npart, siglas.get(npart), nom, leg, None))
                comp = int((detalhe.get(c) or {}).get("comparecimento") or 0)
                ap = int(aptos.get(a["ele"]) or 0)
                nulos = a["nulo"] + a["fora"]
                tot = a["nom"] + a["leg"] + a["branco"] + nulos
                dvs.append((ANO, TURNO, a["ele"], TIPO, DATA, sg, ibge.get(mun), mun, str(zona), str(secao), CARGO_BI[c],
                            ap, comp, max(ap - comp, 0), a["nom"], a["branco"], nulos, a["leg"], a["fora"],
                            pct(comp, ap), pct(a["nom"], tot), pct(a["leg"], tot), pct(a["branco"], tot), pct(nulos, tot), None))
        # SEMPRE apaga as secoes do lote antes de inserir: se o processo morreu
        # entre o commit no BI e a marca no Postgres, o reenvio nao duplica.
        grupos: dict[tuple, list[str]] = {}
        for p in pend:
            grupos.setdefault((p["cod_mun"], str(p["zona"])), []).append(str(p["secao"]))
        for (mun_g, zona_g), secoes_g in grupos.items():
            marc = ",".join(["%s"] * len(secoes_g))
            for t in ("resultados_candidato_secao", "resultados_partido_secao", "detalhes_votacao_secao"):
                bi_apagar(con, f"DELETE FROM {t} WHERE ano = 2026 AND sigla_uf = %s AND id_municipio_tse = %s "
                               f"AND zona = %s AND secao IN ({marc})", (sg, mun_g, zona_g, *secoes_g))
        base = ["ano", "turno", "id_eleicao", "tipo_eleicao", "data_eleicao", "sigla_uf", "id_municipio", "id_municipio_tse", "zona", "secao", "cargo"]
        n = bi_inserir(con, "resultados_candidato_secao", base + ["numero_partido", "sigla_partido", "titulo_eleitoral_candidato",
                       "sequencial_candidato", "numero_candidato", "votos"], rcs)
        n += bi_inserir(con, "resultados_partido_secao", base + ["numero_partido", "sigla_partido", "votos_nominais", "votos_legenda", "etl_id"], rps)
        n += bi_inserir(con, "detalhes_votacao_secao", base + ["aptos", "comparecimento", "abstencoes", "votos_nominais",
                        "votos_brancos", "votos_nulos", "votos_legenda", "votos_nulos_apu_sep", "proporcao_comparecimento",
                        "proporcao_votos_nominais", "proporcao_votos_legenda", "proporcao_votos_brancos",
                        "proporcao_votos_nulos", "etl_id"], dvs)
        con.commit()
        await pg.executemany(
            "INSERT INTO bi_sync_secao (cod_mun, zona, secao, hash, linhas, enviado_em) VALUES ($1,$2,$3,$4,$5,NOW()) "
            "ON CONFLICT (cod_mun, zona, secao) DO UPDATE SET hash=EXCLUDED.hash, linhas=EXCLUDED.linhas, enviado_em=NOW()",
            [(p["cod_mun"], p["zona"], p["secao"], p["hash"], 0) for p in pend])
        total += n
        await batimento(etapa="secoes", linhas=total)
        print(f"[bi] secoes: +{len(pend)} ({n} linhas) | acumulado {total} linhas", flush=True)


# ---------------------------------------------------------------- laco

async def rodada(pg, redis, client) -> dict:
    ibge = await mapa_ibge(pg)
    con = bi_conectar()
    feito = {}
    try:
        for etapa in ETAPAS:
            t0 = time.monotonic()
            if etapa == "locais":
                n = await etapa_locais(pg, con, ibge)
            elif etapa == "candidatos":
                n = await etapa_candidatos(pg, con, client)
            elif etapa == "bens":
                n = await etapa_bens(pg, con, client)
            elif etapa == "perfil":
                n = await etapa_perfil(pg, con, client, ibge)
            elif etapa == "receitas":
                n = await etapa_receitas(pg, con, client)
            elif etapa == "despesas":
                n = await etapa_despesas(pg, con, client)
            elif etapa == "lugares":
                n = await etapa_lugares(pg, con, ibge)
            elif etapa == "secoes":
                n = await etapa_secoes(pg, con, ibge)
            else:
                continue
            feito[etapa] = n
            print(f"[bi] etapa {etapa}: {n} linhas em {time.monotonic() - t0:.0f}s", flush=True)
            await redis.set(HEARTBEAT, json.dumps({"ts": time.time(), "etapa": etapa, **feito}), ex=INTERVALO * 4)
    finally:
        con.close()
    if any(feito.values()):
        await redis.set(AGG_PENDENTE, str(time.time()))
    return feito


async def main() -> None:
    if not (POSTGRES_URL and REDIS_URL and BI["password"]):
        print("[bi] faltam POSTGRES_URL / REDIS_URL / BI_DB_PASS", file=sys.stderr)
        sys.exit(1)
    DIR_TSE.mkdir(parents=True, exist_ok=True)
    pg = await asyncpg.connect(POSTGRES_URL)
    await pg.execute(DDL)
    redis = aioredis.from_url(REDIS_URL)
    global _REDIS
    _REDIS = redis
    async with httpx.AsyncClient(headers={"User-Agent": "Megatron/1.0"}, follow_redirects=True) as client:
        while True:
            try:
                print(f"[bi] rodada ok: {await rodada(pg, redis, client)}", flush=True)
            except Exception as e:  # noqa: BLE001 — loga e tenta na proxima rodada
                print(f"[bi] ERRO na rodada: {e!r}", file=sys.stderr, flush=True)
            await redis.set(HEARTBEAT, json.dumps({"ts": time.time(), "ocioso": True}), ex=INTERVALO * 4)
            await asyncio.sleep(INTERVALO)


if __name__ == "__main__":
    asyncio.run(main())
