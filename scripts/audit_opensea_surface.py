#!/usr/bin/env python3
"""Exercise OpenSea's useful read surfaces for catalog and Hubzz evidence.

This is an evidence/enrichment audit, not a trading client. It measures which
OpenSea read surfaces resolve for catalog collections, preserves mutable market
facts with an observation timestamp, samples recent NFT identities from events,
and compares indexed NFT metadata with OpenSea's direct-chain validation view.
No result promotes a VRM without the catalog's separate binary validator.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.opensea_client import OpenSeaClient

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_OUT = ROOT / "data" / "opensea_surface_report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def contract_from_row(row: sqlite3.Row) -> str:
    return text(row["contract"]).lower() if "contract" in row.keys() else ""


def token_identity(event: dict[str, Any]) -> tuple[str, str, str] | None:
    nft = event.get("nft") or event.get("asset") or {}
    if not isinstance(nft, dict):
        return None
    chain = text(nft.get("chain"))
    contract = text(nft.get("contract") or nft.get("contract_address"))
    token_id = text(nft.get("identifier") or nft.get("token_id"))
    if chain and contract and token_id:
        return chain, contract.lower(), token_id
    return None


async def safe(label: str, fn, *args, **kwargs) -> tuple[Any, str | None]:
    try:
        return await fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{label}: {type(exc).__name__}: {exc}"[:500]


async def inspect_collection(client: OpenSeaClient, row: sqlite3.Row, sample_nfts: int) -> dict[str, Any]:
    slug = text(row["opensea_slug"])
    result: dict[str, Any] = {
        "catalogId": text(row["id"]),
        "name": text(row["name"]),
        "slug": slug,
        "chain": text(row["chain"]),
        "contract": contract_from_row(row),
        "observedAt": now_iso(),
        "collection": None,
        "stats": None,
        "traits": None,
        "recentEvents": None,
        "bestListings": None,
        "collectionOffers": None,
        "sampledNfts": [],
        "errors": [],
    }
    if not slug:
        result["errors"].append("missing_opensea_slug")
        return result

    calls = [
        ("collection", client.get_collection, (slug,), {}),
        ("stats", client.get_collection_stats, (slug,), {}),
        ("traits", client.get_collection_traits, (slug,), {}),
        ("recentEvents", client.get_collection_events, (slug,), {"limit": max(10, sample_nfts * 3)}),
        ("bestListings", client.get_best_listings, (slug,), {"limit": 10}),
        ("collectionOffers", client.get_collection_offers, (slug,), {"limit": 10}),
    ]
    values = await asyncio.gather(*(safe(label, fn, *args, **kwargs) for label, fn, args, kwargs in calls))
    for (label, _fn, _args, _kwargs), (value, error) in zip(calls, values):
        result[label] = value
        if error:
            result["errors"].append(error)

    identities: list[tuple[str, str, str]] = []
    event_data = result.get("recentEvents") or {}
    events = event_data.get("asset_events") or event_data.get("events") or []
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            ident = token_identity(event)
            if ident and ident not in identities:
                identities.append(ident)
            if len(identities) >= sample_nfts:
                break

    if not identities:
        nfts, error = await safe("collection_nfts", client.get_collection_nfts, slug, limit=sample_nfts)
        if error:
            result["errors"].append(error)
        for nft in (nfts or {}).get("nfts") or []:
            if not isinstance(nft, dict):
                continue
            chain = text(nft.get("chain")) or text(row["chain"])
            contract = text(nft.get("contract") or result["contract"])
            token_id = text(nft.get("identifier") or nft.get("token_id"))
            if chain and contract and token_id:
                ident = (chain, contract.lower(), token_id)
                if ident not in identities:
                    identities.append(ident)
            if len(identities) >= sample_nfts:
                break

    for chain, contract, token_id in identities[:sample_nfts]:
        nft, e1 = await safe("nft", client.get_nft, chain, contract, token_id)
        metadata, e2 = await safe("metadata", client.get_nft_metadata, chain, contract, token_id)
        validation, e3 = await safe(
            "validate_metadata", client.validate_nft_metadata, chain, contract, token_id,
            ignore_cached_item_urls=True,
        )
        collection, e4 = await safe("nft_collection", client.get_nft_collection, chain, contract, token_id)
        sample = {
            "chain": chain,
            "contract": contract,
            "tokenId": token_id,
            "nft": nft,
            "metadata": metadata,
            "metadataValidation": validation,
            "collectionIdentity": collection,
            "errors": [e for e in (e1, e2, e3, e4) if e],
        }
        result["sampledNfts"].append(sample)

    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM collections WHERE opensea_slug IS NOT NULL AND trim(opensea_slug) != '' ORDER BY name"
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]

    async with OpenSeaClient(max_concurrency=args.concurrency) as client:
        chains, chain_error = await safe("chains", client.get_chains)
        gate = asyncio.Semaphore(args.collection_concurrency)

        async def bounded(row: sqlite3.Row) -> dict[str, Any]:
            async with gate:
                return await inspect_collection(client, row, args.sample_nfts)

        collections = await asyncio.gather(*(bounded(row) for row in rows))

    summary = {
        "collectionsInspected": len(collections),
        "collectionsWithDedicatedBanner": sum(
            bool(text((item.get("collection") or {}).get("banner_image_url"))) for item in collections
        ),
        "sampledNfts": sum(len(item["sampledNfts"]) for item in collections),
        "metadataValidationCalls": sum(len(item["sampledNfts"]) for item in collections),
        "collectionsWithErrors": sum(bool(item["errors"]) for item in collections),
        "surfaceErrorClasses": dict(Counter(
            error.split(":", 1)[0]
            for item in collections
            for error in item["errors"]
        )),
        "supportedChainsReturned": len((chains or {}).get("chains") or []),
    }
    if chain_error:
        summary["chainsError"] = chain_error
    return {
        "schema": "opensea-surface-audit-v1",
        "generatedAt": now_iso(),
        "purpose": "catalog-and-hubzz-read-surface-audit",
        "summary": summary,
        "chains": chains,
        "collections": collections,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sample-nfts", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--collection-concurrency", type=int, default=3)
    args = ap.parse_args()
    report = asyncio.run(run(args))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
