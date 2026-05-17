import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import json
from unittest.mock import AsyncMock
from publisher import publish

@pytest.mark.asyncio
async def test_publish_chama_xadd():
    mock_redis = AsyncMock()
    await publish(mock_redis, "megatron:sp:governador", {"pst": "50%"})
    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == "megatron:sp:governador"
    assert "timestamp" in call_args[0][1]
    assert "data" in call_args[0][1]

@pytest.mark.asyncio
async def test_publish_usa_maxlen():
    mock_redis = AsyncMock()
    await publish(mock_redis, "megatron:sp:governador", {"pst": "50%"})
    call_kwargs = mock_redis.xadd.call_args[1]
    assert call_kwargs.get("maxlen") == 1000

@pytest.mark.asyncio
async def test_publish_serializa_json():
    mock_redis = AsyncMock()
    data = {"pst": "73.45%", "hor": "22:05:00"}
    await publish(mock_redis, "megatron:sp:governador", data)
    fields = mock_redis.xadd.call_args[0][1]
    parsed = json.loads(fields["data"])
    assert parsed == data
