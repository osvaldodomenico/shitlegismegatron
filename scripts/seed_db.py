#!/usr/bin/env python3
"""
Inicializa o banco TimescaleDB do MEGATRON:
- Habilita extensão timescaledb
- Cria tabela snapshots
- Converte em hypertable (particionado por tempo)
"""
import os
import sys

import psycopg2

POSTGRES_URL = os.environ.get("POSTGRES_URL")

CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS snapshots (
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uf          TEXT NOT NULL,
    cargo       TEXT NOT NULL,
    pst_pct     NUMERIC(5, 2),
    payload     JSONB
);
"""

CREATE_HYPERTABLE = """
SELECT create_hypertable('snapshots', 'time', if_not_exists => TRUE);
"""

def seed() -> None:
    if not POSTGRES_URL:
        print("[seed_db] POSTGRES_URL não definida. Encerrando.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("[seed_db] Habilitando extensão timescaledb...")
    cur.execute(CREATE_EXTENSION)

    print("[seed_db] Criando tabela snapshots...")
    cur.execute(CREATE_TABLE)

    print("[seed_db] Convertendo em hypertable...")
    cur.execute(CREATE_HYPERTABLE)

    cur.close()
    conn.close()
    print("[seed_db] Banco inicializado com sucesso.")

if __name__ == "__main__":
    seed()
