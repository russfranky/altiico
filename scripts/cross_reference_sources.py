#!/usr/bin/env python3
"""Cross-reference catalog/OpenSea facts with Moralis NFT data.

This script never promotes a VRM candidate by itself. It produces source-stamped
corroboration and conflict evidence for collection identity, media, supply,
ownership and market activity so downstream exporters can distinguish consensus
from single-source claims.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.moralis_client import CHAIN_MAP, MoralisClient  # noqa: E402

DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_OUT = ROOT / "data" / "source_cross_reference_report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def same_text(a: Any, b: Any) -> bool | None:
    left, right = text(a).casefold(), text(b).casefold()
    if not left or not right:
        return None
    return left == right


def near_number(a: Any, b: Any, tolerance: float = 0.02) -> bool | None:
    left, right = as_float(a), as_float(b)
    if left is None or right is None:
        return None
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) / scale <= tolerance


def compare(field: str, catalog: Any, moralis: Any, *, numeric: bool = False) -> dict[str, Any]:
    agrees = near_number(catalog, moralis) if numeric else same_text(catalog, moralis)
    return {"field": field, "catalogOrOpenSea": catalog, "moralis": moralis, "agrees": agrees}


async def safe(label: str, fn, *args, **kwargs) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return await fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{label}: {type(exc).__name__}: {exc}"[:500]


async def inspect(client: MoralisClient, row: sqlite3.Row) -> dict[str, Any]:
    chain = text(row["chain"]).lower()
    contract = text(row["contract"]).lower()
    observed = now_iso()
    result: dict[str, Any] = {
        "catalogId": text(row["id"]),
        "name": text(row["name"]),
        "chain": chain,
        "contract": contract,
        "observedAt": observed,
        "moralis": {},
        "comparisons": [],
        "conflicts": [],
        "errors": [],
    }
    if chain not in CHAIN_MAP or not contract.startswith("0x"):
        result["errors"].append("unsupported_or_missing_evm_contract")
        return result

    calls = await asyncio.gather(
        safe("metadata", client.collection_metadata, chain, contract),
        safe("stats", client.collection_stats, chain, contract),
        safe("floor", client.collection_floor, chain, contract),
        safe("nfts", client.collection_nfts, chain, contract, limit=3),
        safe("owners", client.collection_owners, chain, contract, limit=1),
        safe("trades", client.collection_trades, chain, contract, limit=3),
    )
    labels = ("metadata", "stats", "floor", "nfts", "owners", "trades")
    for label, (value, error) in zip(labels, calls):
        result["moralis"][label] = value
        if error:
            result["errors"].append(error)

    meta = result["moralis"].get("metadata") or {}
    stats = result["moralis"].get("stats") or {}
    floor = result["moralis"].get("floor") or {}

    comparisons = [
        compare("name", row["name"], meta.get("name")),
        compare("total_supply", row["total_supply"] if "total_supply" in row.keys() else None, stats.get("total_tokens"), numeric=True),
        compare("num_owners", row["num_owners"] if "num_owners" in row.keys() else None, (stats.get("owners") or {}).get("current"), numeric=True),
        compare("banner_image_url", row["banner_image_url"] if "banner_image_url" in row.keys() else None, meta.get("collection_banner_image")),
        compare("image_url", row["image_url"] if "image_url" in row.keys() else None, meta.get("collection_logo")),
        compare("floor_price", row["floor_price"] if "floor_price" in row.keys() else None, floor.get("floor_price"), numeric=True),
    ]
    result["comparisons"] = comparisons
    result["conflicts"] = [item for item in comparisons if item["agrees"] is False]

    nft_rows = (result["moralis"].get("nfts") or {}).get("result") or []
    samples: list[dict[str, Any]] = []
    for nft in nft_rows[:3]:
        if not isinstance(nft, dict):
            continue
        samples.append({
            "tokenId": text(nft.get("token_id")),
            "tokenUri": nft.get("token_uri"),
            "metadata": nft.get("normalized_metadata") or nft.get("metadata"),
            "possibleSpam": nft.get("possible_spam"),
            "verifiedCollection": nft.get("verified_collection"),
            "lastMetadataSync": nft.get("last_metadata_sync"),
            "lastTokenUriSync": nft.get("last_token_uri_sync"),
            "lastSale": nft.get("last_sale"),
            "listPrice": nft.get("list_price"),
        })
    result["moralis"]["sampledNfts"] = samples

    result["corroboration"] = {
        "contractQueriedDirectly": True,
        "moralisVerifiedCollection": meta.get("verified_collection"),
        "moralisPossibleSpam": meta.get("possible_spam"),
        "identityAgreement": all(item["agrees"] is not False for item in comparisons if item["field"] == "name"),
        "supplyAgreement": next((item["agrees"] for item in comparisons if item["field"] == "total_supply"), None),
        "ownerAgreement": next((item["agrees"] for item in comparisons if item["field"] == "num_owners"), None),
        "mediaAgreement": all(item["agrees"] is not False for item in comparisons if item["field"] in {"banner_image_url", "image_url"}),
        "marketAgreement": next((item["agrees"] for item in comparisons if item["field"] == "floor_price"), None),
        "independentOnchainSignals": {
            "ownerCount": (stats.get("owners") or {}).get("current"),
            "transferCount": (stats.get("transfers") or {}).get("total"),
            "recentTradesReturned": len((result["moralis"].get("trades") or {}).get("result") or []),
        },
        "note": "Moralis floor pricing may itself aggregate marketplace APIs including OpenSea; treat ownership, transfer and onchain trade signals as more independent than floor-price agreement.",
    }
    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM collections ORDER BY name").fetchall()
    rows = [r for r in rows if text(r["chain"]).lower() in CHAIN_MAP and text(r["contract"]).startswith("0x")]
    if args.limit:
        rows = rows[: args.limit]

    async with MoralisClient(max_concurrency=args.concurrency) as client:
        gate = asyncio.Semaphore(args.collection_concurrency)

        async def bounded(row: sqlite3.Row) -> dict[str, Any]:
            async with gate:
                return await inspect(client, row)

        collections = await asyncio.gather(*(bounded(row) for row in rows))

    comparisons = [c for item in collections for c in item["comparisons"]]
    conflicts = [c for item in collections for c in item["conflicts"]]
    summary = {
        "collectionsInspected": len(collections),
        "collectionsWithErrors": sum(bool(item["errors"]) for item in collections),
        "collectionsWithConflicts": sum(bool(item["conflicts"]) for item in collections),
        "fieldComparisons": len(comparisons),
        "fieldConflicts": len(conflicts),
        "agreementByField": {},
    }
    for field in sorted({c["field"] for c in comparisons}):
        values = [c["agrees"] for c in comparisons if c["field"] == field and c["agrees"] is not None]
        summary["agreementByField"][field] = {
            "compared": len(values),
            "agreed": sum(v is True for v in values),
            "conflicted": sum(v is False for v in values),
        }
    return {
        "schema": "catalog-source-cross-reference-v1",
        "generatedAt": now_iso(),
        "sources": {
            "catalog": "data/vrm_index.db",
            "opensea": "catalog fields refreshed through OpenSea API where available",
            "moralis": "Moralis Web3 Data API v2.2",
        },
        "policy": {
            "immutableIdentity": "contract and chain require direct evidence; a marketplace index may corroborate but does not override validated discovery evidence",
            "mutableMarketData": "timestamp each source independently and preserve disagreements",
            "vrmPromotion": "never promote from marketplace/index metadata alone; binary GLB/VRM validation remains required",
            "floorIndependenceCaveat": "Moralis floor price can include OpenSea marketplace data and is not considered an independent source by itself",
        },
        "summary": summary,
        "collections": collections,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--collection-concurrency", type=int, default=3)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
