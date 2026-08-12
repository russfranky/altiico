from __future__ import annotations

import asyncio
import time

import pytest

import scripts.opensea_client as module
from scripts.opensea_client import MAX_ATTEMPTS, OpenSeaClient


class FakeResponse:
    def __init__(self, status: int, *, headers=None, payload=None, text=""):
        self.status = status
        self.headers = headers or {}
        self._payload = payload if payload is not None else {}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.closed = False
        self.calls = 0

    def request(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)

    async def close(self):
        self.closed = True


def test_environment_key_precedes_local_file(monkeypatch, tmp_path):
    path = tmp_path / "api_key"
    path.write_text("file-key", encoding="utf-8")
    monkeypatch.setenv("OPENSEA_API_KEY", "env-key")
    client = OpenSeaClient(str(path))
    assert client._headers["X-API-KEY"] == "env-key"


def test_missing_key_is_explicit(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENSEA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        OpenSeaClient(str(tmp_path / "missing"))


def test_reset_header_uses_unix_time(monkeypatch):
    waits = []

    async def fake_sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(time, "time", lambda: 1_000.0)
    client = OpenSeaClient(api_key="test", sleeper=fake_sleep)
    asyncio.run(client._sleep_until_reset("1007.5"))
    assert waits == [7.5]


def test_429_retry_budget_is_bounded(monkeypatch):
    waits = []

    async def fake_sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(module.random, "uniform", lambda _a, _b: 0.0)
    responses = [
        FakeResponse(429, headers={"Retry-After": "0"}, text="limited")
        for _ in range(MAX_ATTEMPTS)
    ]
    client = OpenSeaClient(api_key="test", sleeper=fake_sleep)
    client._session = FakeSession(responses)

    with pytest.raises(RuntimeError, match="retry budget exhausted"):
        asyncio.run(client.get_collection("example"))
    assert client._session.calls == MAX_ATTEMPTS
    assert len(waits) == MAX_ATTEMPTS - 1


def test_successful_request_obeys_reset_after_releasing_response(monkeypatch):
    waits = []

    async def fake_sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(time, "time", lambda: 2_000.0)
    client = OpenSeaClient(api_key="test", sleeper=fake_sleep)
    client._session = FakeSession(
        [
            FakeResponse(
                200,
                headers={"X-RateLimit-Remaining": "1", "X-RateLimit-Reset": "2003"},
                payload={"ok": True},
            )
        ]
    )
    result = asyncio.run(client.get_collection("example"))
    assert result == {"ok": True}
    assert waits == [3.0]


def test_catalog_read_surfaces_use_current_routes():
    client = OpenSeaClient(api_key="test")
    calls = []
    async def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"ok": True}
    client._request = fake_request
    async def exercise():
        await client.get_chains()
        await client.get_collection_traits("avatars")
        await client.get_collection_events("avatars", limit=200)
        await client.get_nft_collection("ethereum", "0xabc", "1")
        await client.get_nft_metadata("ethereum", "0xabc", "1")
        await client.validate_nft_metadata("ethereum", "0xabc", "1", ignore_cached_item_urls=True)
        await client.get_best_listings("avatars", limit=10)
        await client.get_collection_offers("avatars", limit=10)
    asyncio.run(exercise())
    routes = [(method, url) for method, url, _ in calls]
    assert ("GET", "/chains") in routes
    assert ("GET", "/traits/avatars") in routes
    assert ("GET", "/events/collection/avatars") in routes
    assert ("GET", "/chain/ethereum/contract/0xabc/nfts/1/collection") in routes
    assert ("GET", "/metadata/ethereum/0xabc/1") in routes
    assert ("POST", "/chain/ethereum/contract/0xabc/nfts/1/validate-metadata") in routes
    assert ("GET", "/listings/collection/avatars/best") in routes
    assert ("GET", "/offers/collection/avatars") in routes
