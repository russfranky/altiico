import pytest
from aiohttp import web

from scripts import etherscan_client
from scripts.etherscan_client import EtherscanClient


@pytest.mark.asyncio
async def test_api_level_rate_limit_is_retried(monkeypatch):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return web.json_response(
                {
                    "status": "0",
                    "message": "NOTOK",
                    "result": "Max calls per sec rate limit reached (3/sec)",
                }
            )
        return web.json_response(
            {"status": "1", "message": "OK", "result": [{"ContractName": "Example"}]}
        )

    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(etherscan_client, "BASE_URL", f"http://127.0.0.1:{port}/")
    monkeypatch.setattr(etherscan_client, "_retry_delay", lambda attempt: 0.0)

    try:
        async with EtherscanClient(
            "test-key", max_concurrency=1, min_request_interval=0
        ) as client:
            result = await client.source_code("ethereum", "0xabc")
    finally:
        await runner.cleanup()

    assert calls == 2
    assert result == [{"ContractName": "Example"}]


@pytest.mark.asyncio
async def test_non_rate_limit_api_error_is_not_retried(monkeypatch):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return web.json_response(
            {"status": "0", "message": "NOTOK", "result": "Invalid API Key"}
        )

    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(etherscan_client, "BASE_URL", f"http://127.0.0.1:{port}/")

    try:
        async with EtherscanClient(
            "test-key", max_concurrency=1, min_request_interval=0
        ) as client:
            with pytest.raises(RuntimeError, match="Invalid API Key"):
                await client.source_code("ethereum", "0xabc")
    finally:
        await runner.cleanup()

    assert calls == 1


@pytest.mark.asyncio
async def test_unverified_contract_is_empty_result_not_error(monkeypatch):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return web.json_response(
            {
                "status": "0",
                "message": "NOTOK",
                "result": "Contract source code not verified",
            }
        )

    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(etherscan_client, "BASE_URL", f"http://127.0.0.1:{port}/")

    try:
        async with EtherscanClient(
            "test-key", max_concurrency=1, min_request_interval=0
        ) as client:
            result = await client.source_code("ethereum", "0xabc")
    finally:
        await runner.cleanup()

    assert calls == 1
    assert result == []
