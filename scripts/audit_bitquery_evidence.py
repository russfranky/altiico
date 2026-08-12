#!/usr/bin/env python3
"""Cross-check catalog NFT contracts against Bitquery on-chain transfer/URI data."""
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

from scripts.bitquery_client import BitqueryClient, NETWORK_MAP  # noqa: E402

DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_OUT = ROOT / "data" / "bitquery_evidence_report.json"
MODEL_EXTENSIONS = (".vrm", ".glb", ".gltf")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def model_signals(value: Any, path: str = "$") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(model_signals(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            found.extend(model_signals(child, f"{path}[{idx}]"))
    elif isinstance(value, str):
        lower = value.lower()
        if any(ext in lower for ext in MODEL_EXTENSIONS) or "vrm" in lower:
            found.append({"path": path, "value": value[:1000]})
    return found


async def inspect(client: BitqueryClient, row: sqlite3.Row, token_limit: int) -> dict[str, Any]:
    chain = text(row["chain"]).lower()
    contract = text(row["contract"]).lower()
    result: dict[str, Any] = {
        "catalogId": text(row["id"]),
        "name": text(row["name"]),
        "chain": chain,
        "contract": contract,
        "observedAt": now_iso(),
        "supported": chain in NETWORK_MAP,
        "contractObservedOnchain": False,
        "tokensSampled": 0,
        "uniqueTokenIds": 0,
        "transferUris": 0,
        "modelSignals": [],
        "sampledTransfers": [],
        "errors": [],
    }
    if chain not in NETWORK_MAP or not contract.startswith("0x"):
        return result
    try:
        data = await client.nft_inventory(chain, contract, limit=token_limit)
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"{type(exc).__name__}: {exc}"[:700])
        return result

    transfers = ((data.get("EVM") or {}).get("Transfers") or []) if isinstance(data, dict) else []
    ids: set[str] = set()
    for item in transfers:
        if not isinstance(item, dict):
            continue
        transfer = item.get("Transfer") or {}
        currency = transfer.get("Currency") or {}
        token_id = text(transfer.get("Id"))
        uri = text(transfer.get("URI"))
        if token_id:
            ids.add(token_id)
        if uri:
            result["transferUris"] += 1
        signals = model_signals({"uri": uri, "data": transfer.get("Data")})
        if signals:
            result["modelSignals"].append({
                "tokenId": token_id or None,
                "signals": signals,
            })
        if len(result["sampledTransfers"]) < 8:
            result["sampledTransfers"].append({
                "tokenId": token_id or None,
                "uri": uri or None,
                "name": currency.get("Name"),
                "symbol": currency.get("Symbol"),
                "protocol": currency.get("ProtocolName"),
                "sender": transfer.get("Sender"),
                "receiver": transfer.get("Receiver"),
                "block": (item.get("Block") or {}).get("Number"),
                "time": (item.get("Block") or {}).get("Time"),
                "txHash": (item.get("Transaction") or {}).get("Hash"),
            })
    result["tokensSampled"] = len(transfers)
    result["uniqueTokenIds"] = len(ids)
    result["contractObservedOnchain"] = bool(transfers)
    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM collections ORDER BY name").fetchall()
    rows = [r for r in rows if text(r["chain"]).lower() in NETWORK_MAP and text(r["contract"]).startswith("0x")]
    if args.limit:
        rows = rows[: args.limit]
    async with BitqueryClient(max_concurrency=args.concurrency) as client:
        gate = asyncio.Semaphore(args.collection_concurrency)
        async def bounded(row: sqlite3.Row) -> dict[str, Any]:
            async with gate:
                return await inspect(client, row, args.tokens)
        collections = await asyncio.gather(*(bounded(row) for row in rows))

    return {
        "schema": "bitquery-nft-evidence-v1",
        "generatedAt": now_iso(),
        "source": "Bitquery API v2 EVM Transfers",
        "policy": {
            "role": "independent on-chain transfer, NFT identity and token URI corroboration",
            "vrmPromotion": "Bitquery URI/model signals are candidates only; binary GLB 2.0 plus VRM/VRMC_vrm validation remains required",
        },
        "summary": {
            "collectionsInspected": len(collections),
            "collectionsObservedOnchain": sum(bool(x["contractObservedOnchain"]) for x in collections),
            "collectionsWithErrors": sum(bool(x["errors"]) for x in collections),
            "tokensSampled": sum(int(x["tokensSampled"]) for x in collections),
            "transferUris": sum(int(x["transferUris"]) for x in collections),
            "modelSignalTokens": sum(len(x["modelSignals"]) for x in collections),
        },
        "collections": collections,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tokens", type=int, default=50)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--collection-concurrency", type=int, default=2)
    args = ap.parse_args()
    report = asyncio.run(run(args))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
