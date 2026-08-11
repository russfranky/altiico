#!/usr/bin/env python3
"""Centralized OpenSea API v2 client.

Credentials are server-side only: ``OPENSEA_API_KEY`` is preferred, with
``~/.opensea/api_key`` retained as a local-development fallback. Requests use a
small concurrency gate, bounded retries, Retry-After handling, and correct Unix
rate-reset arithmetic.
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import aiohttp

from scripts.chain_registry import OPENSEA_CHAIN_MAP as CHAIN_MAP

BASE_URL = "https://api.opensea.io/api/v2"


MAX_ATTEMPTS = 6
MAX_SINGLE_RETRY_DELAY = 60.0
MAX_CUMULATIVE_RETRY_DELAY = 180.0


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class OpenSeaClient:
    """Async OpenSea API v2 client with bounded, rate-aware requests."""

    def __init__(
        self,
        api_key_path: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        max_concurrency: int = 2,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        path = Path(api_key_path) if api_key_path else Path.home() / ".opensea" / "api_key"
        resolved = (api_key or os.environ.get("OPENSEA_API_KEY") or "").strip()
        if not resolved and path.exists():
            resolved = path.read_text(encoding="utf-8").strip()
        if not resolved:
            raise RuntimeError(
                "OpenSea API key is not configured; set OPENSEA_API_KEY or "
                f"create {path}"
            )
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._api_key = resolved
        self._headers = {
            "Accept": "application/json",
            "X-API-KEY": self._api_key,
            "User-Agent": "vrm-catalog/1.0",
        }
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._sleep = sleeper

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Issue a request with finite retry and rate-limit budgets."""
        session = await self._get_session()
        cumulative_retry_delay = 0.0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                full_url = url if url.startswith("http") else BASE_URL + url
                retry_delay: float | None = None
                payload: Any = None
                reset_after_success: str | None = None

                async with self._semaphore:
                    async with session.request(
                        method, full_url, params=params, json=json_body
                    ) as resp:
                        remaining = resp.headers.get("X-RateLimit-Remaining")
                        limit = resp.headers.get("X-RateLimit-Limit")
                        reset = resp.headers.get("X-RateLimit-Reset")
                        status = resp.status
                        _log(
                            f"[opensea] {method} {url} -> {status} "
                            f"(attempt={attempt}/{MAX_ATTEMPTS}, remaining={remaining}/{limit})"
                        )

                        if status == 429:
                            if attempt >= MAX_ATTEMPTS:
                                body = await resp.text()
                                raise RuntimeError(
                                    f"OpenSea retry budget exhausted after HTTP 429: {body[:200]}"
                                )
                            retry_after = resp.headers.get("Retry-After", "5")
                            try:
                                retry_delay = float(retry_after)
                            except (TypeError, ValueError):
                                retry_delay = 5.0
                            retry_delay = min(
                                MAX_SINGLE_RETRY_DELAY,
                                max(0.0, retry_delay) + random.uniform(0, 1),
                            )
                        elif 500 <= status < 600:
                            if attempt >= MAX_ATTEMPTS:
                                raise RuntimeError("OpenSea retry budget exhausted")
                            retry_delay = min(
                                MAX_SINGLE_RETRY_DELAY,
                                (2**attempt) + random.uniform(0, 1),
                            )
                        elif status >= 400:
                            body = await resp.text()
                            raise RuntimeError(
                                f"OpenSea API error {status} for {method} {url}: {body[:300]}"
                            )
                        else:
                            payload = await resp.json()
                            if remaining is not None and reset:
                                try:
                                    if int(remaining) <= 1:
                                        reset_after_success = reset
                                except ValueError:
                                    pass

                if retry_delay is not None:
                    cumulative_retry_delay += retry_delay
                    if cumulative_retry_delay > MAX_CUMULATIVE_RETRY_DELAY:
                        raise RuntimeError("OpenSea cumulative retry delay budget exhausted")
                    _log(f"[opensea] retrying after {retry_delay:.1f}s")
                    await self._sleep(retry_delay)
                    continue

                if reset_after_success:
                    await self._sleep_until_reset(reset_after_success)
                return payload

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt >= MAX_ATTEMPTS:
                    raise RuntimeError("OpenSea retry budget exhausted") from exc
                delay = min(
                    MAX_SINGLE_RETRY_DELAY,
                    (2**attempt) + random.uniform(0, 1),
                )
                cumulative_retry_delay += delay
                if cumulative_retry_delay > MAX_CUMULATIVE_RETRY_DELAY:
                    raise RuntimeError("OpenSea cumulative retry delay budget exhausted") from exc
                _log(f"[opensea] {type(exc).__name__}: {exc}, backoff {delay:.1f}s")
                await self._sleep(delay)

        raise RuntimeError("OpenSea retry budget exhausted")

    async def _sleep_until_reset(self, reset: str) -> None:
        """Sleep until OpenSea's Unix-epoch ``X-RateLimit-Reset`` value."""
        try:
            reset_ts = float(reset)
        except (TypeError, ValueError):
            return
        wait = min(MAX_SINGLE_RETRY_DELAY, max(0.0, reset_ts - time.time()))
        if wait > 0:
            _log(f"[opensea] rate bucket nearly empty, sleeping {wait:.1f}s until reset")
            await self._sleep(wait)

    async def search(
        self,
        query: str,
        *,
        chain: Optional[str] = None,
        asset_type: str = "collection",
        limit: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": query,
            "asset_types": asset_type,
            "limit": max(1, min(int(limit), 50)),
        }
        if chain:
            params["chains"] = CHAIN_MAP.get(chain, chain)
        return await self._request("GET", "/search", params=params)

    async def get_collection(self, slug: str) -> dict[str, Any]:
        return await self._request("GET", f"/collections/{slug}")

    async def get_collection_stats(self, slug: str) -> dict[str, Any]:
        return await self._request("GET", f"/collections/{slug}/stats")

    async def get_nft(
        self, chain: str, contract: str, token_id: str
    ) -> dict[str, Any]:
        os_chain = CHAIN_MAP.get(chain, chain)
        return await self._request(
            "GET", f"/chain/{os_chain}/contract/{contract}/nfts/{token_id}"
        )

    async def get_collection_nfts(
        self, slug: str, cursor: Optional[str] = None, *, limit: int = 100
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 100))}
        if cursor:
            params["next"] = cursor
        return await self._request("GET", f"/collection/{slug}/nfts", params=params)

    async def batch_collections(self, slugs: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST", "/collections/batch", json_body={"slugs": slugs}
        )

    async def get_contract_nfts(
        self, chain: str, contract: str, cursor: Optional[str] = None
    ) -> dict[str, Any]:
        os_chain = CHAIN_MAP.get(chain, chain)
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["next"] = cursor
        return await self._request(
            "GET", f"/chain/{os_chain}/contract/{contract}/nfts", params=params
        )


def run_async(coro: Any) -> Any:
    return asyncio.run(coro)
