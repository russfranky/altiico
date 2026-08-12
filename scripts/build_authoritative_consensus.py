#!/usr/bin/env python3
"""Combine OpenSea/Moralis consensus with Etherscan and Bitquery on-chain evidence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CROSS = ROOT / "data/source_consensus.json"
ETH = ROOT / "data/etherscan_authority_report.json"
BIT = ROOT / "data/bitquery_evidence_report.json"
OUT = ROOT / "data/authoritative_consensus.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def indexed(items: Any) -> dict[str, dict[str, Any]]:
    return {
        item.get("catalogId"): item
        for item in (items or [])
        if isinstance(item, dict) and item.get("catalogId")
    }


def main() -> int:
    consensus = json.loads(CROSS.read_text(encoding="utf-8"))
    etherscan = json.loads(ETH.read_text(encoding="utf-8"))
    bitquery = json.loads(BIT.read_text(encoding="utf-8"))
    etherscan_by_id = indexed(etherscan.get("collections"))
    bitquery_by_id = indexed(bitquery.get("collections"))

    source_collections = consensus.get("collections") or {}
    if isinstance(source_collections, dict):
        source_items: list[dict[str, Any]] = [
            value for value in source_collections.values() if isinstance(value, dict)
        ]
    else:
        source_items = [value for value in source_collections if isinstance(value, dict)]

    review_by_id = indexed(consensus.get("reviewQueue"))
    collections: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for item in source_items:
        cid = item.get("catalogId")
        es = etherscan_by_id.get(cid)
        bq = bitquery_by_id.get(cid)
        existing_review = review_by_id.get(cid) or {}
        source_conflicts = list(existing_review.get("conflictFields") or [])
        source_errors = list(existing_review.get("errors") or [])
        es_conflicts = list((es or {}).get("conflicts") or [])
        es_errors = list((es or {}).get("errors") or [])
        evidence = (es or {}).get("contractEvidence") or {}
        explorer_corroborated = bool(
            evidence.get("creator")
            or evidence.get("verifiedSource")
            or evidence.get("creationTxHash")
            or evidence.get("eventLogsSampled")
        )
        bitquery_corroborated = bool((bq or {}).get("contractObservedOnchain"))
        onchain_corroborated = explorer_corroborated or bitquery_corroborated

        record = {
            **item,
            "etherscan": {
                "observedAt": (es or {}).get("observedAt"),
                "contractCorroborated": explorer_corroborated,
                "verifiedSource": evidence.get("verifiedSource"),
                "contractName": evidence.get("contractName"),
                "proxy": evidence.get("proxy"),
                "implementation": evidence.get("implementation"),
                "creator": evidence.get("creator"),
                "creationTxHash": evidence.get("creationTxHash"),
                "creationBlock": evidence.get("creationBlock"),
                "tokenInfo": evidence.get("tokenInfo"),
                "abiSignals": evidence.get("abiSignals"),
                "eventLogsSampled": evidence.get("eventLogsSampled"),
                "errors": es_errors,
                "conflicts": es_conflicts,
            },
            "bitquery": {
                "observedAt": (bq or {}).get("observedAt"),
                "contractObservedOnchain": bitquery_corroborated,
                "tokensSampled": (bq or {}).get("tokensSampled", 0),
                "uniqueTokenIds": (bq or {}).get("uniqueTokenIds", 0),
                "transferUris": (bq or {}).get("transferUris", 0),
                "modelSignals": (bq or {}).get("modelSignals") or [],
                "sampledTransfers": (bq or {}).get("sampledTransfers") or [],
                "errors": (bq or {}).get("errors") or [],
            },
            "authorityStatus": (
                "onchain_corroborated" if onchain_corroborated else "index_only_or_unavailable"
            ),
        }
        collections.append(record)

        if source_conflicts or source_errors or es_conflicts or es_errors:
            identity = item.get("identity") or {}
            review.append(
                {
                    "catalogId": cid,
                    "name": identity.get("canonicalName"),
                    "chain": identity.get("chain"),
                    "contract": identity.get("contract"),
                    "sourceConflicts": source_conflicts,
                    "sourceErrors": source_errors,
                    "etherscanConflicts": es_conflicts,
                    "etherscanErrors": es_errors,
                    "bitqueryErrors": (bq or {}).get("errors") or [],
                }
            )

    payload = {
        "schema": "authoritative-catalog-consensus-v2",
        "generatedAt": now_iso(),
        "policy": {
            "identity": "chain+contract are anchored by direct discovery/on-chain evidence; Etherscan contract/deployment evidence and Bitquery transfer history corroborate identity; OpenSea/Moralis indexes never silently override it",
            "mutableFields": "preserve per-source timestamps and conflicts",
            "vrm": "only binary GLB 2.0 + VRM/VRMC_vrm validation proves VRM",
            "market": "market values are mutable and source-specific",
            "bitquery": "Bitquery transfer URI/model signals are discovery evidence only until the referenced bytes pass binary validation",
        },
        "summary": {
            "collections": len(collections),
            "explorerCorroborated": sum(bool(item["etherscan"]["contractCorroborated"]) for item in collections),
            "bitqueryCorroborated": sum(bool(item["bitquery"]["contractObservedOnchain"]) for item in collections),
            "onchainCorroborated": sum(item["authorityStatus"] == "onchain_corroborated" for item in collections),
            "bitqueryModelSignalTokens": sum(len(item["bitquery"]["modelSignals"]) for item in collections),
            "reviewItems": len(review),
            "etherscanConflicts": sum(len(item["etherscanConflicts"]) for item in review),
        },
        "collections": collections,
        "reviewQueue": review,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
