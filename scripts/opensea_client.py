#!/usr/bin/env python3
"""Centralized OpenSea API v2 client with token-bucket rate limiting,
Retry-After handling, and exponential backoff. All other scripts should
import from here instead of re-implementing."""

from __future__ import annotations

import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Any, Optional

import aiohttp

BASE_URL = "https://api.opensea.io/api/v2"

CHAIN_MAP: dict[str, str] = {
    "ethereum": "ethereum",
    "polygon": "matic",
    "base": "base",
    "optimism": "optimism",
    "shape": "shape",
    "arbitrum": "arbitrum",
    "sepolia": "sepolia",
}

MAX_ATTEMPTS = 6


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class OpenSeaClient:
    """Async OpenSea API v2 client with token-bucket rate limiting."""

    def __init__(self, api_key_path: Optional[str] = None) -> None:
        path = Path(api_key_path) if api_key_path else Path.home() / ".opensea" / "api_key"
        self._api_key = path.read_text().strip()
        self._headers = {
            "Accept": "application/json",
            "X-API-KEY": self._api_key,
        }
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------ session

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=BASE_URL,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "OpenSeaClient":
        await self._get_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ----------------------------------------------------------------- requests

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Issue a request with rate-limit awareness, 429 retry, and 5xx backoff."""
        session = await self._get_session()
        attempt = 0
        while True:
            attempt += 1
            try:
                async with session.request(
                    method, url, params=params, json=json_body
                ) as resp:
                    remaining = resp.headers.get("X-RateLimit-Remaining")
                    limit = resp.headers.get("X-RateLimit-Limit")
                    reset = resp.headers.get("X-RateLimit-Reset")
                    status = resp.status

                    _log(
                        f"[opensea] {method} {url} -> {status} "
                        f"(remaining={remaining}/{limit})"
                    )

                    # Pre-emptive rate-limit sleep before yielding the response
                    if remaining is not None:
                        try:
                            rem_int = int(remaining)
                        except ValueError:
                            rem_int = None
                        if rem_int is not None and rem_int <= 1 and reset:
                            await self._sleep_until_reset(reset)

                    if status == 429:
                        retry_after = resp.headers.get("Retry-After", "5")
                        try:
                            wait = float(retry_after)
                        except ValueError:
                            wait = 5.0
                        wait += random.uniform(0, 1)
                        _log(f"[opensea] 429 rate limited, sleeping {wait:.1f}s")
                        await asyncio.sleep(wait)
                        continue

                    if 500 <= status < 600:
                        if attempt >= MAX_ATTEMPTS:
                            raise RuntimeError("OpenSea retry budget exhausted")
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        _log(f"[opensea] {status} server error, backoff {backoff:.1f}s")
                        await asyncio.sleep(backoff)
                        continue

                    if status >= 400:
                        body = await resp.text()
                        raise RuntimeError(
                            f"OpenSea API error {status} for {method} {url}: {body[:300]}"
                        )

                    return await resp.json()

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt >= MAX_ATTEMPTS:
                    raise RuntimeError("OpenSea retry budget exhausted") from e
                backoff = (2 ** attempt) + random.uniform(0, 1)
                _log(f"[opensea] {type(e).__name__}: {e}, backoff {backoff:.1f}s")
                await asyncio.sleep(backoff)

    async def _sleep_until_reset(self, reset: str) -> None:
        """Sleep until the epoch-second reset time given by X-RateLimit-Reset."""
        try:
            reset_ts = float(reset)
        except (TypeError, ValueError):
            return
        wait = max(0.0, reset_ts - asyncio.get_event_loop().time())
        if wait > 0:
            _log(f"[opensea] rate bucket nearly empty, sleeping {wait:.1f}s until reset")
            await asyncio.sleep(wait)

    # ------------------------------------------------------------------- public

    async def get_collection(self, slug: str) -> dict[str, Any]:
        """GET /collections/{slug} — collection metadata."""
        return await self._request("GET", f"/collections/{slug}")

    async def get_collection_stats(self, slug: str) -> dict[str, Any]:
        """GET /collections/{slug}/stats — floor, volume, owner counts."""
        return await self._request("GET", f"/collections/{slug}/stats")

    async def get_nft(
        self, chain: str, contract: str, token_id: str
    ) -> dict[str, Any]:
        """GET /chain/{chain}/contract/{contract}/nfts/{token_id} — single NFT."""
        os_chain = CHAIN_MAP.get(chain, chain)
        return await self._request(
            "GET",
            f"/chain/{os_chain}/contract/{contract}/nfts/{token_id}",
        )

    async def get_collection_nfts(
        self, slug: str, cursor: Optional[str] = None
    ) -> dict[str, Any]:
        """GET /collection/{slug}/nfts — paginated NFT list (limit=100)."""
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["next"] = cursor
        return await self._request(
            "GET", f"/collection/{slug}/nfts", params=params
        )

    async def batch_collections(self, slugs: list[str]) -> dict[str, Any]:
        """POST /collections/batch — metadata for multiple slugs at once."""
        return await self._request(
            "POST", "/collections/batch", json_body={"slugs": slugs}
        )

    async def get_contract_nfts(
        self, chain: str, contract: str, cursor: Optional[str] = None
    ) -> dict[str, Any]:
        """GET /chain/{chain}/contract/{contract}/nfts — paginated NFT list (limit=100)."""
        os_chain = CHAIN_MAP.get(chain, chain)
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["next"] = cursor
        return await self._request(
            "GET",
            f"/chain/{os_chain}/contract/{contract}/nfts",
            params=params,
        )


def run_async(coro: Any) -> Any:
    """Sync wrapper for CLI usage — runs a coroutine to completion."""
    return asyncio.run(coro)
