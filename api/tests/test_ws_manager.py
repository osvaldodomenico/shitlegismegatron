import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock
from ws_manager import ConnectionManager

@pytest.mark.asyncio
async def test_connect_aceita_websocket_e_adiciona_a_room():
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()
    await mgr.connect(ws, "sp:governador")
    ws.accept.assert_called_once()
    assert ws in mgr.rooms["sp:governador"]

@pytest.mark.asyncio
async def test_disconnect_remove_da_room():
    mgr = ConnectionManager()
    ws = MagicMock()
    ws.accept = AsyncMock()
    await mgr.connect(ws, "sp:governador")
    mgr.disconnect(ws, "sp:governador")
    assert ws not in mgr.rooms["sp:governador"]

@pytest.mark.asyncio
async def test_broadcast_envia_para_todos_na_room():
    mgr = ConnectionManager()
    ws1, ws2 = MagicMock(), MagicMock()
    ws1.accept = AsyncMock()
    ws2.accept = AsyncMock()
    ws1.send_text = AsyncMock()
    ws2.send_text = AsyncMock()
    await mgr.connect(ws1, "sp:governador")
    await mgr.connect(ws2, "sp:governador")
    await mgr.broadcast("sp:governador", '{"pst":"50%"}')
    ws1.send_text.assert_called_once_with('{"pst":"50%"}')
    ws2.send_text.assert_called_once_with('{"pst":"50%"}')

@pytest.mark.asyncio
async def test_broadcast_nao_falha_para_room_vazia():
    mgr = ConnectionManager()
    # não deve lançar exceção
    await mgr.broadcast("rj:presidente", '{"pst":"0%"}')
