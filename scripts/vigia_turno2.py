#!/usr/bin/env python3
"""
VIGIA DO 2o TURNO (25/10/2026) — cron do host a cada 30 min.

Le o indice oficial do TSE (ele-c.json, UMA requisicao por execucao: a CDN
devolve 429 se apertar) e procura a eleicao do presidente no 2o turno
(ELE_2T_BR = 6258, turno "2"). O TSE publica o 2o turno como um PLEITO NOVO
(em 2024: pleito 453, 27/10, eleicao 620) — o codigo desse pleito e o
URNA_PLEITO dos boletins de urna, o unico dado que falta para ligar a coleta.

Quando achar (uma vez so):
  - grava /opt/megatron/.env.turno2 com o bloco do 2o turno ja preenchido;
  - manda e-mail (mesmo canal do reanimador) com o comando para ligar.
NAO liga nada sozinho: quem liga e scripts/ligar_turno2.sh.
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

INDICE = "https://resultados.tse.jus.br/oficial/comum/config/ele-c.json"
ELE_2T_BR = os.environ.get("ELE_2T_BR", "6258")
RAIZ = Path(__file__).resolve().parent.parent
ENV_T2 = RAIZ / ".env.turno2"
MARCA = Path("/var/tmp/megatron-turno2.publicado")
ENVFILE = Path(os.environ.get("MEGATRON_RESEND_ENV", "/root/.disk_guard.env"))
MAILTO = os.environ.get("MEGATRON_MAILTO", "osvaldodomenico.apple@gmail.com")
MAILFROM = "MEGATRON <alertas@certificacao.shiftlegis.com.br>"


def log(msg: str) -> None:
    print(f"{datetime.now().isoformat(timespec='seconds')} {msg}", flush=True)


def baixar_indice() -> dict:
    req = urllib.request.Request(INDICE, headers={
        "User-Agent": "Megatron/1.0 (Election Monitor)", "Accept": "application/json",
        "Referer": "https://resultados.tse.jus.br/"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def achar_turno2(indice: dict) -> dict | None:
    for p in indice.get("pl") or []:
        for e in p.get("e") or []:
            if str(e.get("cd")) == ELE_2T_BR and str(e.get("t")) == "2":
                return {"pleito": str(p.get("cd")), "data": p.get("dt") or "",
                        "nome": html.unescape(e.get("nm") or "")}
    return None


def data_iso(dt_br: str) -> str:
    d, m, a = dt_br.split("/")
    return f"{a}-{m}-{d}"


def enviar(assunto: str, corpo: str) -> None:
    chave = ""
    if ENVFILE.exists():
        for linha in ENVFILE.read_text().splitlines():
            if linha.startswith("RESEND_KEY="):
                chave = linha.split("=", 1)[1].strip().strip('"')
    if not chave:
        log("sem RESEND_KEY: e-mail nao enviado")
        return
    dados = json.dumps({"from": MAILFROM, "to": [MAILTO], "subject": assunto, "text": corpo})
    r = subprocess.run(["curl", "-sS", "-m", "20", "-X", "POST", "https://api.resend.com/emails",
                        "-H", f"Authorization: Bearer {chave}", "-H", "Content-Type: application/json",
                        "-d", dados], capture_output=True, text=True)
    log(f"e-mail: {r.stdout.strip() or r.stderr.strip()}")


def main() -> int:
    if MARCA.exists():
        return 0  # ja avisou; nada a fazer
    try:
        t2 = achar_turno2(baixar_indice())
    except Exception as e:  # noqa: BLE001 — TSE fora/429: tenta na proxima
        log(f"indice indisponivel: {e!r}")
        return 0
    if not t2:
        log(f"2o turno ainda nao publicado (procurando eleicao {ELE_2T_BR}, turno 2)")
        return 0

    ENV_T2.write_text(f"""# === 2o TURNO — gerado pelo vigia_turno2 em {datetime.now():%d/%m/%Y %H:%M} ===
# {t2['nome']} — pleito {t2['pleito']}, {t2['data']}
# Aplicado por scripts/ligar_turno2.sh (anexa ao .env; desfazer: scripts/desligar_turno2.sh)
POSTGRES_DB_COLETA=megatron_t2
URNA_SUBDIR=urnas_t2
URNA_PLEITO={t2['pleito']}
ELE_1T_BR={ELE_2T_BR}
MUN_CARGOS=presidente
BI_TURNO=2
BI_DATA={data_iso(t2['data'])}
BI_ELE_BR={ELE_2T_BR}
BI_ETAPAS=lugares,secoes
""")
    MARCA.write_text(json.dumps(t2))
    log(f"2o TURNO PUBLICADO: pleito {t2['pleito']} ({t2['data']}) — {ENV_T2} gravado")
    enviar("MEGATRON: TSE publicou o 2o turno — pronto para ligar",
           f"""O TSE publicou o 2o turno no indice oficial.

Eleicao: {t2['nome']}
Pleito (URNA_PLEITO): {t2['pleito']}
Data: {t2['data']}

Configuracao pronta em {ENV_T2}.
Para ligar a coleta do 2o turno (MEGATRON -> Legis Inteligencia), na VPS BI:
  /opt/megatron/scripts/ligar_turno2.sh
Para voltar ao 1o turno:
  /opt/megatron/scripts/desligar_turno2.sh

Roteiro completo: Obsidian > Megatron > 08 - Historico (05/10, preparo do 2o turno).""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
