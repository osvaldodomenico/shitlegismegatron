import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import respx
import httpx
from fetcher import fetch_if_changed, _snapshots

@pytest.fixture(autouse=True)
def clear_snapshots():
    _snapshots.clear()
    yield
    _snapshots.clear()

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_dados_na_primeira_chamada():
    url = "http://tse.example.com/resultado.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={"pst": "10%", "e": [], "hor": "10:00:00"}))
    async with httpx.AsyncClient() as client:
        result = await fetch_if_changed(client, url)
    assert result is not None
    assert result["pst"] == "10%"

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_none_quando_dados_iguais():
    url = "http://tse.example.com/resultado.json"
    payload = {"pst": "10%", "e": [], "hor": "10:00:00"}
    respx.get(url).mock(return_value=httpx.Response(200, json=payload))
    async with httpx.AsyncClient() as client:
        await fetch_if_changed(client, url)
        result = await fetch_if_changed(client, url)
    assert result is None

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_dados_quando_muda():
    url = "http://tse.example.com/resultado.json"
    respx.get(url).mock(side_effect=[
        httpx.Response(200, json={"pst": "10%", "e": [], "hor": "10:00:00"}),
        httpx.Response(200, json={"pst": "20%", "e": [], "hor": "10:01:00"}),
    ])
    async with httpx.AsyncClient() as client:
        await fetch_if_changed(client, url)
        result = await fetch_if_changed(client, url)
    assert result is not None
    assert result["pst"] == "20%"

@respx.mock
@pytest.mark.asyncio
async def test_fetch_retorna_none_quando_schema_invalido():
    url = "http://tse.example.com/resultado.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={"foo": "bar"}))
    async with httpx.AsyncClient() as client:
        result = await fetch_if_changed(client, url)
    assert result is None
