#!/usr/bin/env python3
"""Search OpenSea at NFT level for high-signal VRM and 3D avatar leads.

This complements collection search. Search hits are resolved to full NFT records,
their original metadata is fetched and recursively scanned, and only binaries
that pass GLB + VRM validation are counted as VRMs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_opensea_candidates import _inspect_nft, _text  # noqa: E402
from scripts.opensea_client import CHAIN_MAP, OpenSeaClient  # noqa: E402

DEFAULT_QUERIES = ("VRM", "VRM avatar", "GLB avatar", "glTF avatar", "3D avatar")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unwrap_nft(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("nft")
    return nested if isinstance(nested, dict) else row


def _address(row: dict[str, Any]) -> str:
    for key in ("contract", "contract_address", "address"):
        value = row.get(key)
        if isinstance(value, str) and value.startswith("0x"):
            return value.lower()
        if isinstance(value, dict):
            address = value.get("address") or value.get("contract_address")
            if isinstance(address, str) and address.startswith("0x"):
                return address.lower()
    return ""


def _token_id(row: dict[str, Any]) -> str:
    return _text(row.get("identifier") or row.get("token_id") or row.get("tokenId"))


def _chain(row: dict[str, Any], fallback: str) -> str:
    raw = row.get("chain")
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, dict):
        value = raw.get("identifier") or raw.get("name") or raw.get("slug")
        if value:
            return str(value)
    return fallback


def _collection_slug(row: dict[str, Any]) -> str:
    value = row.get("collection")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _text(value.get("collection") or value.get("slug") or value.get("name"))
    return _text(row.get("collection_slug") or row.get("slug"))


def _search_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "nfts", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


async def discover(args: argparse.Namespace) -> dict[str, Any]:
    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]
    client = OpenSeaClient(max_concurrency=2)
    hits: dict[str, dict[str, Any]] = {}
    search_requests = 0
    unresolved_search_hits = 0

    try:
        for query in queries:
            for requested_chain in chains:
                try:
                    data = await client.search(
                        query,
                        chain=requested_chain,
                        asset_type="nft",
                        limit=args.search_limit,
                    )
                    search_requests += 1
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"NFT search failed query={query!r} chain={requested_chain}: {exc}",
                        file=sys.stderr,
                    )
                    continue

                for outer in _search_rows(data):
                    row = _unwrap_nft(outer)
                    address = _address(row)
                    identifier = _token_id(row)
                    chain = _chain(row, requested_chain)
                    if not address or not identifier:
                        unresolved_search_hits += 1
                        continue
                    key = f"{chain}:{address}:{identifier}"
                    hit = hits.setdefault(key, {
                        "key": key,
                        "chain": chain,
                        "contract": address,
                        "token_id": identifier,
                        "collection": _collection_slug(row),
                        "name": _text(row.get("name")),
                        "queries": set(),
                        "search_payload": row,
                        "full_nft": None,
                        "metadata_fetched": False,
                        "metadata_error": None,
                        "model_candidates": [],
                        "validated_vrms": [],
                        "rejected_model_candidates": [],
                        "error": None,
                    })
                    hit["queries"].add(query)

        ranked = list(hits.values())[: args.max_nfts]
        print(
            f"NFT-level search produced {len(hits)} resolved unique NFT leads; "
            f"inspecting {len(ranked)}",
            file=sys.stderr,
        )
        gate = asyncio.Semaphore(args.nft_concurrency)

        async def inspect(hit: dict[str, Any]) -> None:
            async with gate:
                try:
                    nft = await client.get_nft(
                        hit["chain"], hit["contract"], hit["token_id"]
                    )
                    if isinstance(nft.get("nft"), dict):
                        nft = nft["nft"]
                    if not isinstance(nft, dict):
                        raise RuntimeError("OpenSea NFT response was not an object")
                    hit["full_nft"] = nft
                except Exception as exc:  # noqa: BLE001
                    hit["error"] = f"get_nft: {type(exc).__name__}: {exc}"[:500]
                    return

                result = await asyncio.to_thread(_inspect_nft, nft, args.timeout)
                hit["metadata_fetched"] = bool(result["metadata_fetched"])
                hit["metadata_error"] = result["metadata_error"]
                hit["model_candidates"] = result["model_candidates"]
                for validation in result["validations"]:
                    if validation.get("valid"):
                        hit["validated_vrms"].append(validation)
                    else:
                        hit["rejected_model_candidates"].append(validation)
                if hit["validated_vrms"]:
                    print(
                        f"NFT VRM HIT {hit['chain']}:{hit['contract']}:{hit['token_id']} "
                        f"({len(hit['validated_vrms'])})",
                        file=sys.stderr,
                    )

        await asyncio.gather(*(inspect(hit) for hit in ranked))
    finally:
        await client.close()

    ranked = list(hits.values())[: args.max_nfts]
    for hit in ranked:
        hit["queries"] = sorted(hit["queries"])
        # Avoid storing a redundant full OpenSea payload in the artifact.
        hit.pop("full_nft", None)

    valid = [v for hit in ranked for v in hit["validated_vrms"]]
    rejected = [v for hit in ranked for v in hit["rejected_model_candidates"]]
    summary = {
        "search_requests": search_requests,
        "queries": len(queries),
        "chains": len(chains),
        "unique_resolved_nft_leads": len(hits),
        "nfts_inspected": len(ranked),
        "unresolved_search_hits": unresolved_search_hits,
        "metadata_documents_fetched": sum(bool(hit["metadata_fetched"]) for hit in ranked),
        "metadata_fetch_errors": sum(bool(hit["metadata_error"]) for hit in ranked),
        "nfts_with_model_candidates": sum(bool(hit["model_candidates"]) for hit in ranked),
        "model_candidates": sum(len(hit["model_candidates"]) for hit in ranked),
        "nfts_with_validated_vrms": sum(bool(hit["validated_vrms"]) for hit in ranked),
        "validated_vrms": len(valid),
        "rejected_model_candidates": len(rejected),
        "validation_statuses": dict(Counter(v["status"] for v in [*valid, *rejected])),
    }
    return {
        "schema": "opensea-nft-discovery-v1",
        "generated_at": utc_now(),
        "summary": summary,
        "nfts": ranked,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search OpenSea NFT results for VRM leads.")
    ap.add_argument(
        "--output",
        default=str(_REPO_ROOT / "data" / "opensea_nft_discovery_report.json"),
    )
    ap.add_argument("--queries", default=",".join(DEFAULT_QUERIES))
    ap.add_argument("--chains", default="ethereum,polygon,base,arbitrum,optimism")
    ap.add_argument("--search-limit", type=int, default=50)
    ap.add_argument("--max-nfts", type=int, default=300)
    ap.add_argument("--nft-concurrency", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args(argv)

    if not os.getenv("OPENSEA_API_KEY") and not (Path.home() / ".opensea" / "api_key").exists():
        print("OpenSea credential missing", file=sys.stderr)
        return 2

    report = asyncio.run(discover(args))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
