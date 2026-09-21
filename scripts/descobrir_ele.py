#!/usr/bin/env python3
"""
Descobre os codigos de eleicao (ELE) publicados pelo TSE.

O TSE publica um INDICE OFICIAL em /oficial/comum/config/ele-c.json, com cada
pleito, sua data e o codigo de cada turno. Ler esse indice e muito melhor do
que sondar a CDN as cegas: a versao anterior deste script varria os codigos
500..700, faixa correta em 2022 (544/546) e ERRADA hoje — em 2026 os codigos
ja estao na casa dos 6200 (6262..6272). No dia da eleicao a varredura nao
acharia nada e a gente procuraria bug no lugar errado.

O indice cobre o ciclo corrente e os recentes (hoje: 2024..2026). Nao alcanca
2022, entao a validacao e contra a municipal de 2024 — evento real mais
recente e no esquema atual:
    06/10/2024  ELE_1T=619  ELE_2T=620  Eleicao Ordinaria Municipal

Uso:
    scripts/descobrir_ele.py                 # pleitos de 2026
    scripts/descobrir_ele.py --ano 2024 --gerais    # auto-teste
    scripts/descobrir_ele.py --ano 2026 --json
    scripts/descobrir_ele.py --gerais        # ignora suplementares
"""
import argparse
import html
import json
import sys
import urllib.request

INDICE = "https://resultados.tse.jus.br/oficial/comum/config/ele-c.json"
HEADERS = {
    "User-Agent": "Megatron/1.0 (Election Monitor)",
    "Accept": "application/json",
    "Referer": "https://resultados.tse.jus.br/",
}
TIMEOUT = 25


def baixar_indice(url: str = INDICE) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def pleitos(indice: dict, ano: str = "", so_gerais: bool = False) -> list[dict]:
    """
    Achata o indice em uma lista de eleicoes.

    `tp` do pleito distingue o tipo; suplementares trazem "Suplementar" no
    nome. Filtrar por nome e mais estavel do que confiar no codigo de tipo,
    que ja mudou entre ciclos.
    """
    saida = []
    for p in indice.get("pl") or []:
        data = p.get("dt") or ""
        for e in p.get("e") or []:
            nome = html.unescape(e.get("nm") or "")
            if ano and not data.endswith(ano):
                continue
            if so_gerais and "suplementar" in nome.lower():
                continue
            saida.append({
                "data": data,
                "nome": nome,
                "ele_1t": e.get("cd") or "",
                "ele_2t": e.get("cdt2") or "",
                "turno": e.get("t") or "",
                "abrangencias": [a.get("cd") for a in (e.get("abr") or [])],
                "cargos": sorted({
                    c.get("ds") for a in (e.get("abr") or [])
                    for c in (a.get("cp") or []) if c.get("ds")
                }),
            })
    saida.sort(key=lambda x: tuple(reversed((x["data"] or "//").split("/"))))
    return saida


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ano", default="2026")
    ap.add_argument("--gerais", action="store_true",
                    help="ignora eleicoes suplementares")
    ap.add_argument("--json", action="store_true")
    # Usados pelo vigia_ele.sh. Ficam aqui, e nao como python inline no shell,
    # porque escapar aspas dentro de `python3 -c '...'` ja quebrou uma vez —
    # e quebrou EM SILENCIO, deixando o vigia sem nunca alarmar.
    ap.add_argument("--resumo-geral", action="store_true",
                    help="texto dos pleitos NAO suplementares; vazio se nao houver")
    ap.add_argument("--assinatura", action="store_true",
                    help="hash do conjunto de pleitos, para detectar mudanca")
    args = ap.parse_args()

    try:
        indice = baixar_indice()
    except Exception as e:
        print(f"[descobrir_ele] falha ao ler o indice do TSE: {e}", file=sys.stderr)
        return 2

    achados = pleitos(indice, ano=args.ano, so_gerais=args.gerais)

    if args.assinatura:
        import hashlib
        chave = "|".join(sorted(
            f"{p['data']}:{p['ele_1t']}:{p['ele_2t']}" for p in achados))
        print(hashlib.md5(chave.encode()).hexdigest())
        return 0

    if args.resumo_geral:
        gerais = [p for p in achados if "suplementar" not in p["nome"].lower()]
        for p in gerais:
            print(f"{p['data']}  ELE_1T={p['ele_1t']}  "
                  f"ELE_2T={p['ele_2t'] or '-'}  {p['nome']}")
            if p["cargos"]:
                print(f"    cargos: {', '.join(p['cargos'])}")
        return 0 if gerais else 1

    if args.json:
        print(json.dumps({"ciclo": indice.get("c"), "gerado": indice.get("dg"),
                          "pleitos": achados}, ensure_ascii=False, indent=1))
        return 0 if achados else 1

    print(f"Indice do TSE — ciclo corrente: {indice.get('c')} "
          f"(gerado em {indice.get('dg')} {indice.get('hg')})")
    print(f"Pleitos de {args.ano}"
          f"{' (so gerais)' if args.gerais else ''}: {len(achados)}\n")

    if not achados:
        print("Nenhum pleito encontrado. O TSE ainda nao publicou este ciclo.")
        return 1

    for a in achados:
        print(f"  {a['data']}  ELE_1T={a['ele_1t']}"
              f"{'  ELE_2T=' + a['ele_2t'] if a['ele_2t'] else ''}")
        print(f"      {a['nome']}")
        if a["cargos"]:
            print(f"      cargos: {', '.join(a['cargos'])}")
        if a["abrangencias"]:
            abr = a["abrangencias"]
            print(f"      abrangencias: {len(abr)} ({', '.join(abr[:6])}"
                  f"{'…' if len(abr) > 6 else ''})")

    # Para eleicao geral, o codigo nacional (presidente) e o por UF sao
    # diferentes: o TSE publica pleitos separados no mesmo dia.
    print("\nPara o .env do MEGATRON, use o pleito GERAL do dia da eleicao:")
    print("  ELE_1T_BR=<codigo do pleito que tem 'Presidente' nos cargos>")
    print("  ELE_1T=<codigo do pleito que tem 'Governador' nos cargos>")
    print("  ELE_2T=<ELE_2T do mesmo pleito>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
