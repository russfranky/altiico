#!/usr/bin/env python3
"""Small async Bitquery GraphQL client for independent NFT on-chain evidence."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any, Optional

import aiohttp

ENDPOINT = "https://streaming.bitquery.io/graphql"
MAX_ATTEMPTS = 3
NETWORK_MAP = {
    "ethereum": "eth",
    "polygon": "matic",
    "base": "base",
    "arbitrum": "arbitrum",
    "optimism": "optimism",
}


class BitqueryClient:
    def __init__(self, token: Optional[str] = None, *, max_concurrency: int = 3) -> None:
        value = (
            token
            or os.getenv("BITQUERY_API_KEY")
            or os.getenv("BITQUERY_TOKEN")
            or os.getenv("BITQUERY_OAUTH_TOKEN")
            or ""
        ).strip()
        if not value:
            raise RuntimeError("Bitquery API token is not configured")
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {value}",
            "User-Agent": "vrm-catalog/1.0",
        }
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=20),
            )
        return self._session

    async def __aenter__(self) -> "BitqueryClient":
        await self._get_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def network(chain: str) -> str:
        try:
            return NETWORK_MAP[chain.lower()]
        except KeyError as exc:
            raise ValueError(f"Bitquery network not configured for chain: {chain}") from exc

    async def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        session = await self._get_session()
        payload = {"query": query, "variables": variables}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with self._semaphore:
                    async with session.post(ENDPOINT, json=payload) as response:
                        body = await response.text()
                        if response.status == 429 or 500 <= response.status < 600:
                            if attempt == MAX_ATTEMPTS:
                                raise RuntimeError(f"Bitquery retry budget exhausted: HTTP {response.status}")
                            retry_after = response.headers.get("Retry-After")
                            try:
                                delay = float(retry_after) if retry_after else min(8.0, 2 ** attempt)
                            except ValueError:
                                delay = min(8.0, 2 ** attempt)
                            await asyncio.sleep(delay + random.uniform(0, 0.3))
                            continue
                        if response.status >= 400:
                            raise RuntimeError(f"Bitquery HTTP {response.status}: {body[:400]}")
                        data = await response.json()
                if not isinstance(data, dict):
                    raise RuntimeError("Bitquery returned a non-object response")
                if data.get("errors"):
                    raise RuntimeError(f"Bitquery GraphQL error: {str(data['errors'])[:500]}")
                result = data.get("data")
                return result if isinstance(result, dict) else {}
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError("Bitquery retry budget exhausted") from exc
                await asyncio.sleep(min(8.0, 2 ** attempt) + random.uniform(0, 0.3))
        raise RuntimeError("Bitquery retry budget exhausted")

    async def nft_inventory(self, chain: str, contract: str, *, limit: int = 25) -> dict[str, Any]:
        """Return recent NFT transfers for routine corroboration.

        The repository's Bitquery plan currently exposes realtime data. Historical
        archive/combined inventory scans stay a separate optional deep-discovery
        mode so routine evidence refreshes remain plan-compatible and bounded.
        """
        query = """
        query NFTTransfers($network: evm_network!, $contract: String!, $limit: Int!) {
          EVM(network: $network, dataset: realtime) {
            Transfers(
              where: {Transfer: {Currency: {SmartContract: {is: $contract}}}}
              limit: {count: $limit}
              orderBy: {descending: Block_Time}
            ) {
              Block { Number Time }
              Transaction { Hash }
              Transfer {
                Id
                URI
                Data
                Sender
                Receiver
                Amount
                Type
                Currency { Name Symbol SmartContract }
              }
            }
          }
        }
        """
        return await self.execute(
            query,
            {
                "network": self.network(chain),
                "contract": contract.lower(),
                "limit": max(1, min(int(limit), 100)),
            },
        )
