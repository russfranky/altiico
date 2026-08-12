#!/usr/bin/env python3
"""Cross-check EVM catalog contracts against Etherscan API V2.

Etherscan is used for explorer-level contract evidence: verified source/ABI,
proxy implementation, deployment transaction, token type/info and event logs.
This script never overrides validated VRM binary evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.chain_registry import CHAINS  # noqa: E402
from scripts.etherscan_client import EtherscanClient  # noqa: E402

DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_OUT = ROOT / "data" / "etherscan_authority_report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(v: Any) -> str:
    return str(v or "").strip()


def as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


async def safe(label: str, fn, *args, **kwargs):
    try:
        return await fn(*args, **kwargs), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{label}: {type(exc).__name__}: {exc}"[:500]


def abi_signals(raw: str | None) -> dict[str, bool]:
    if not raw:
        return {"tokenURI": False, "uri": False, "ownerOf": False, "balanceOf": False}
    try:
        abi = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"tokenURI": False, "uri": False, "ownerOf": False, "balanceOf": False}
    names = {str(item.get("name")) for item in abi if isinstance(item, dict) and item.get("name")}
    return {name: name in names for name in ("tokenURI", "uri", "ownerOf", "balanceOf")}


async def inspect(client: EtherscanClient, row: sqlite3.Row) -> dict[str, Any]:
    chain = text(row["chain"]).lower()
    contract = text(row["contract"]).lower()
    result: dict[str, Any] = {
        "catalogId": text(row["id"]), "name": text(row["name"]), "chain": chain,
        "chainId": CHAINS[chain].chain_id if chain in CHAINS else None,
        "contract": contract, "observedAt": now_iso(), "errors": [],
    }
    if chain not in CHAINS or not contract.startswith("0x"):
        result["errors"].append("unsupported_or_missing_evm_contract")
        return result
    source_r, abi_r, creation_r, token_r, logs_r = await asyncio.gather(
        safe("source", client.source_code, chain, contract),
        safe("abi", client.abi, chain, contract),
        safe("creation", client.contract_creation, chain, contract),
        safe("token_info", client.token_info, chain, contract),
        safe("logs", client.logs, chain, contract, offset=25),
    )
    source, e1 = source_r; abi, e2 = abi_r; creation, e3 = creation_r; token_info, e4 = token_r; logs, e5 = logs_r
    result["errors"].extend(e for e in (e1, e2, e3, e4, e5) if e)
    source0 = source[0] if isinstance(source, list) and source else {}
    creation0 = creation[0] if isinstance(creation, list) and creation else {}
    token0 = token_info[0] if isinstance(token_info, list) and token_info else {}
    source_text = text(source0.get("SourceCode"))
    result["contractEvidence"] = {
        "verifiedSource": bool(source_text),
        "sourceSha256": hashlib.sha256(source_text.encode()).hexdigest() if source_text else None,
        "contractName": source0.get("ContractName"),
        "compilerVersion": source0.get("CompilerVersion"),
        "licenseType": source0.get("LicenseType"),
        "proxy": source0.get("Proxy"),
        "implementation": source0.get("Implementation") or None,
        "similarMatch": source0.get("SimilarMatch") or None,
        "abiSignals": abi_signals(abi),
        "creator": creation0.get("contractCreator"),
        "creationTxHash": creation0.get("txHash"),
        "creationBlock": creation0.get("blockNumber"),
        "creationTimestamp": creation0.get("timestamp"),
        "tokenInfo": {
            "name": token0.get("tokenName"), "symbol": token0.get("symbol"),
            "type": token0.get("tokenType"), "totalSupply": token0.get("totalSupply"),
            "blueCheckmark": token0.get("blueCheckmark"), "website": token0.get("website"),
            "description": token0.get("description"),
        } if token0 else None,
        "eventLogsSampled": len(logs or []),
    }
    conflicts: list[dict[str, Any]] = []
    if token0:
        es_name = text(token0.get("tokenName"))
        if es_name and text(row["name"]).casefold() != es_name.casefold():
            conflicts.append({"field": "name", "catalog": row["name"], "etherscan": es_name})
        es_supply = as_int(token0.get("totalSupply"))
        cat_supply = as_int(row["total_supply"] if "total_supply" in row.keys() else None)
        if es_supply is not None and cat_supply is not None and es_supply != cat_supply:
            conflicts.append({"field": "total_supply", "catalog": cat_supply, "etherscan": es_supply})
    result["conflicts"] = conflicts
    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    conn = sqlite3.connect(args.db); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM collections ORDER BY name").fetchall()
    rows = [r for r in rows if text(r["chain"]).lower() in CHAINS and text(r["contract"]).startswith("0x")]
    if args.limit: rows = rows[:args.limit]
    async with EtherscanClient(max_concurrency=args.concurrency) as client:
        gate = asyncio.Semaphore(args.collection_concurrency)
        async def bounded(row):
            async with gate: return await inspect(client, row)
        collections = await asyncio.gather(*(bounded(row) for row in rows))
    return {
        "schema": "etherscan-authority-audit-v1", "generatedAt": now_iso(),
        "source": "Etherscan API V2",
        "policy": "explorer evidence corroborates chain/contract/token facts but never substitutes for direct tokenURI or VRM binary validation",
        "summary": {
            "collectionsInspected": len(collections),
            "collectionsWithErrors": sum(bool(x["errors"]) for x in collections),
            "collectionsWithConflicts": sum(bool(x.get("conflicts")) for x in collections),
            "verifiedSourceContracts": sum(bool((x.get("contractEvidence") or {}).get("verifiedSource")) for x in collections),
            "contractsWithTokenUriAbi": sum(bool(((x.get("contractEvidence") or {}).get("abiSignals") or {}).get("tokenURI") or ((x.get("contractEvidence") or {}).get("abiSignals") or {}).get("uri")) for x in collections),
        },
        "collections": collections,
    }


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--db", default=str(DEFAULT_DB)); ap.add_argument("--output", default=str(DEFAULT_OUT)); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--concurrency", type=int, default=3); ap.add_argument("--collection-concurrency", type=int, default=3)
    args=ap.parse_args(); report=asyncio.run(run(args)); out=Path(args.output); out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n"); print(json.dumps(report["summary"], indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
