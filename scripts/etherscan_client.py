#!/usr/bin/env python3
"""Async Etherscan API V2 client for authoritative EVM contract evidence."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any, Optional

import aiohttp

from scripts.chain_registry import CHAINS

BASE_URL = "https://api.etherscan.io/v2/api"
MAX_ATTEMPTS = 5
RATE_LIMIT_MARKERS = ("rate limit", "max calls per sec", "too many requests")


def _retry_delay(attempt: int) -> float:
    return min(20.0, 2 ** attempt) + random.uniform(0, 0.4)


def _is_rate_limit_message(value: Any) -> bool:
    message = str(value or "").casefold()
    return any(marker in message for marker in RATE_LIMIT_MARKERS)


class EtherscanClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        max_concurrency: int = 3,
        min_request_interval: float = 0.36,
    ) -> None:
        key = (api_key or os.getenv("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_KEY") or "").strip()
        if not key:
            raise RuntimeError("Etherscan API key is not configured")
        self._api_key = key
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._min_request_interval = max(0.0, float(min_request_interval))
        self._pace_lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Accept": "application/json", "User-Agent": "vrm-catalog/1.0"},
                timeout=aiohttp.ClientTimeout(total=35),
            )
        return self._session

    async def __aenter__(self) -> "EtherscanClient":
        await self._get_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def chain_id(chain: str) -> str:
        spec = CHAINS.get(chain.lower())
        if not spec:
            raise ValueError(f"unknown EVM chain: {chain}")
        return str(spec.chain_id)

    async def _pace(self) -> None:
        if not self._min_request_interval:
            return
        loop = asyncio.get_running_loop()
        async with self._pace_lock:
            now = loop.time()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                await asyncio.sleep(delay)
            self._next_request_at = loop.time() + self._min_request_interval

    async def _request(self, chain: str, module: str, action: str, **params: Any) -> Any:
        query = {
            "chainid": self.chain_id(chain),
            "module": module,
            "action": action,
            "apikey": self._api_key,
            **{k: v for k, v in params.items() if v is not None},
        }
        session = await self._get_session()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                retryable_http_status: int | None = None
                await self._pace()
                async with self._semaphore:
                    async with session.get(BASE_URL, params=query) as response:
                        if response.status == 429 or 500 <= response.status < 600:
                            retryable_http_status = response.status
                            data = None
                        elif response.status >= 400:
                            body = await response.text()
                            raise RuntimeError(f"Etherscan HTTP {response.status}: {body[:300]}")
                        else:
                            data = await response.json()
                if retryable_http_status is not None:
                    if attempt == MAX_ATTEMPTS:
                        raise RuntimeError(f"Etherscan retry budget exhausted: HTTP {retryable_http_status}")
                    await asyncio.sleep(_retry_delay(attempt))
                    continue
                if not isinstance(data, dict):
                    raise RuntimeError("Etherscan returned a non-object response")
                # Etherscan uses status=0 for genuine errors, empty results, and plan-level throttling.
                status, message, result = str(data.get("status", "")), str(data.get("message", "")), data.get("result")
                if status == "0" and message.upper() not in {"NO TRANSACTIONS FOUND", "NO RECORDS FOUND"}:
                    detail = result if isinstance(result, str) else message
                    if _is_rate_limit_message(detail) or _is_rate_limit_message(message):
                        if attempt == MAX_ATTEMPTS:
                            raise RuntimeError(f"Etherscan retry budget exhausted: API rate limit: {str(detail)[:300]}")
                        await asyncio.sleep(_retry_delay(attempt))
                        continue
                    raise RuntimeError(f"Etherscan API error: {str(detail)[:300]}")
                return result
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError("Etherscan retry budget exhausted") from exc
                await asyncio.sleep(_retry_delay(attempt))
        raise RuntimeError("Etherscan retry budget exhausted")

    async def source_code(self, chain: str, contract: str) -> list[dict[str, Any]]:
        result = await self._request(chain, "contract", "getsourcecode", address=contract)
        return result if isinstance(result, list) else []

    async def abi(self, chain: str, contract: str) -> str | None:
        result = await self._request(chain, "contract", "getabi", address=contract)
        return result if isinstance(result, str) else None

    async def contract_creation(self, chain: str, contract: str) -> list[dict[str, Any]]:
        result = await self._request(chain, "contract", "getcontractcreation", contractaddresses=contract)
        return result if isinstance(result, list) else []

    async def token_info(self, chain: str, contract: str) -> list[dict[str, Any]]:
        result = await self._request(chain, "token", "tokeninfo", contractaddress=contract)
        return result if isinstance(result, list) else []

    async def logs(self, chain: str, contract: str, *, page: int = 1, offset: int = 50) -> list[dict[str, Any]]:
        result = await self._request(
            chain, "logs", "getLogs", address=contract, fromBlock=0, toBlock="latest",
            page=max(1, int(page)), offset=max(1, min(int(offset), 1000)),
        )
        return result if isinstance(result, list) else []
