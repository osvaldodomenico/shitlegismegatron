import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch, call

def test_seed_sai_sem_postgres_url(monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        import seed_db
        seed_db.seed()
    assert exc.value.code == 1

def test_seed_chama_create_extension(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://fake:fake@localhost/fake")
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    with patch("psycopg2.connect", return_value=mock_conn):
        import importlib, seed_db
        importlib.reload(seed_db)
        seed_db.seed()
    sqls = [c.args[0] for c in mock_cur.execute.call_args_list]
    assert any("timescaledb" in s for s in sqls)
    assert any("snapshots" in s for s in sqls)
    assert any("create_hypertable" in s for s in sqls)
