#!/usr/bin/env python3
"""Small async Moralis EVM NFT client for evidence cross-referencing."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any, Optional

import aiohttp

BASE_URL = "https://deep-index.moralis.io/api/v2.2"
MAX_ATTEMPTS = 5
CHAIN_MAP = {
    "ethereum": "eth",
    "polygon": "polygon",
    "base": "base",
    "optimism": "optimism",
    "arbitrum": "arbitrum",
}


class MoralisClient:
    def __init__(self, api_key: Optional[str] = None, *, max_concurrency: int = 3) -> None:
        key = (api_key or os.getenv("MORALIS_API_KEY") or os.getenv("MORALIS_KEY") or "").strip()
        if not key:
            raise RuntimeError("Moralis API key is not configured")
        self._headers = {"Accept": "application/json", "X-API-Key": key, "User-Agent": "vrm-catalog/1.0"}
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers, timeout=aiohttp.ClientTimeout(total=35))
        return self._session

    async def __aenter__(self) -> "MoralisClient":
        await self._get_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        session = await self._get_session()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with self._semaphore:
                    async with session.get(BASE_URL + path, params=params) as response:
                        if response.status == 429 or 500 <= response.status < 600:
                            if attempt == MAX_ATTEMPTS:
                                raise RuntimeError(f"Moralis retry budget exhausted: HTTP {response.status}")
                            retry_after = response.headers.get("Retry-After")
                            try:
                                delay = float(retry_after) if retry_after else min(20.0, 2 ** attempt)
                            except ValueError:
                                delay = min(20.0, 2 ** attempt)
                            await asyncio.sleep(delay + random.uniform(0, 0.4))
                            continue
                        if response.status >= 400:
                            body = await response.text()
                            raise RuntimeError(f"Moralis API error {response.status}: {body[:300]}")
                        data = await response.json()
                        return data if isinstance(data, dict) else {"result": data}
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError("Moralis retry budget exhausted") from exc
                await asyncio.sleep(min(20.0, 2 ** attempt) + random.uniform(0, 0.4))
        raise RuntimeError("Moralis retry budget exhausted")

    @staticmethod
    def chain(chain: str) -> str:
        return CHAIN_MAP.get(chain.lower(), chain.lower())

    async def collection_metadata(self, chain: str, contract: str) -> dict[str, Any]:
        return await self._get(f"/nft/{contract}/metadata", params={"chain": self.chain(chain)})

    async def collection_stats(self, chain: str, contract: str) -> dict[str, Any]:
        return await self._get(f"/nft/{contract}/stats", params={"chain": self.chain(chain)})

    async def collection_floor(self, chain: str, contract: str) -> dict[str, Any]:
        return await self._get(f"/nft/{contract}/floor-price", params={"chain": self.chain(chain)})

    async def collection_nfts(self, chain: str, contract: str, *, limit: int = 5) -> dict[str, Any]:
        return await self._get(
            f"/nft/{contract}",
            params={"chain": self.chain(chain), "limit": max(1, min(int(limit), 100)), "normalizeMetadata": "true", "media_items": "true"},
        )

    async def collection_owners(self, chain: str, contract: str, *, limit: int = 1) -> dict[str, Any]:
        return await self._get(
            f"/nft/{contract}/owners",
            params={"chain": self.chain(chain), "limit": max(1, min(int(limit), 100))},
        )

    async def collection_trades(self, chain: str, contract: str, *, limit: int = 5) -> dict[str, Any]:
        return await self._get(
            f"/nft/{contract}/trades",
            params={"chain": self.chain(chain), "limit": max(1, min(int(limit), 100)), "nft_metadata": "true"},
        )

    async def nft_metadata(self, chain: str, contract: str, token_id: str) -> dict[str, Any]:
        return await self._get(f"/nft/{contract}/{token_id}", params={"chain": self.chain(chain), "normalizeMetadata": "true", "media_items": "true"})
