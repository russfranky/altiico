#!/usr/bin/env python3
"""Discover VRM-bearing NFT contracts through a Blockscout-indexed EVM chain.

This adapter is intentionally chain-generic. It enumerates ERC-721/ERC-1155
contracts from Blockscout, samples indexed NFT instances, recursively scans the
instance metadata for model pointers, and validates every model-like candidate
with the catalog's binary GLB/VRM validator. It never promotes catalog rows.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.chain_registry import get_chain  # noqa: E402
from scripts.crawler.fetch import NetworkLoader  # noqa: E402
from scripts.crawler.models import CrawlPolicy  # noqa: E402
from scripts.crawler.uri import canonicalize_uri  # noqa: E402
from scripts.discover_metadata_fields import scan_metadata  # noqa: E402

MODEL_EXTENSIONS = (".vrm", ".glb", ".gltf")
UA = "vrm-catalog-blockscout-discovery/1.0"


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def _url(base: str, path: str, params: dict[str, Any] | None = None) -> str:
    value = base.rstrip("/") + "/" + path.lstrip("/")
    if params:
        value += "?" + urllib.parse.urlencode(params)
    return value


def _candidate_urls(instance: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    metadata = instance.get("metadata")
    if isinstance(metadata, (dict, list)):
        for candidate in scan_metadata(metadata):
            url = candidate.get("url")
            if isinstance(url, str) and url:
                out.append({
                    "url": url,
                    "path": str(candidate.get("path") or ""),
                    "field": str(candidate.get("field") or ""),
                    "reason": str(candidate.get("reason") or "metadata"),
                })
    for field in ("animation_url", "media_url", "external_app_url"):
        value = instance.get(field)
        if not isinstance(value, str) or not value:
            continue
        clean = value.lower().split("?", 1)[0].split("#", 1)[0]
        if clean.endswith(MODEL_EXTENSIONS):
            out.append({"url": value, "path": f"instance.{field}", "field": field, "reason": "indexed_media"})
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in out:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        deduped.append(item)
    return deduped


def _validate(url: str, timeout: float) -> dict[str, Any]:
    loader = NetworkLoader(None, CrawlPolicy(timeout=timeout, max_attempts=2, max_vrm_bytes=64 * 1024 * 1024))
    try:
        result = loader.validate_vrm(canonicalize_uri(url))
        return {
            "valid": bool(result.valid),
            "status": result.status,
            "canonical_url": result.canonical_url,
            "transport_url": result.transport_url,
            "vrm_spec": result.vrm_spec,
            "content_sha256": result.content_sha256,
            "bytes": result.observed_length or result.total_length,
            "error": result.error,
        }
    except Exception as exc:  # noqa: BLE001
        return {"valid": False, "status": "validation_error", "canonical_url": url, "error": f"{type(exc).__name__}: {exc}"[:500]}


def discover(args: argparse.Namespace) -> dict[str, Any]:
    chain = get_chain(args.chain)
    if not chain.blockscout_api:
        raise SystemExit(f"chain {chain.key} has no Blockscout API configured")
    base = chain.blockscout_api
    contracts: list[dict[str, Any]] = []
    params: dict[str, Any] = {"type": "ERC-721,ERC-1155"}
    pages = 0
    while len(contracts) < args.max_contracts and pages < args.max_pages:
        data = _get_json(_url(base, "/tokens", params), args.timeout)
        pages += 1
        items = data.get("items") or []
        if isinstance(items, list):
            contracts.extend(item for item in items if isinstance(item, dict))
        nxt = data.get("next_page_params")
        if not isinstance(nxt, dict) or not nxt:
            break
        params = {"type": "ERC-721,ERC-1155", **nxt}
    contracts = contracts[: args.max_contracts]

    rows: list[dict[str, Any]] = []
    for token in contracts:
        address = str(token.get("address") or token.get("address_hash") or "")
        if not address.startswith("0x"):
            continue
        row: dict[str, Any] = {
            "contract": address.lower(),
            "name": token.get("name"),
            "symbol": token.get("symbol"),
            "token_type": token.get("type"),
            "total_supply": token.get("total_supply"),
            "instances_sampled": 0,
            "model_candidates": [],
            "validated_vrms": [],
            "errors": [],
        }
        try:
            data = _get_json(_url(base, f"/tokens/{address}/instances"), args.timeout)
            instances = data.get("items") or []
        except Exception as exc:  # noqa: BLE001
            row["errors"].append(f"instances: {type(exc).__name__}: {exc}"[:500])
            rows.append(row)
            continue
        if not isinstance(instances, list):
            instances = []
        for instance in [item for item in instances if isinstance(item, dict)][: args.sample_instances]:
            row["instances_sampled"] += 1
            token_id = str(instance.get("id") or "")
            for candidate in _candidate_urls(instance):
                validation = _validate(candidate["url"], args.timeout)
                evidence = {**candidate, "token_id": token_id, **validation}
                row["model_candidates"].append(evidence)
                if validation.get("valid"):
                    row["validated_vrms"].append(evidence)
        rows.append(row)
        if row["validated_vrms"]:
            print(f"VRM HIT {chain.key}:{address} {row['name']}: {len(row['validated_vrms'])}", file=sys.stderr)

    validations = [c for row in rows for c in row["model_candidates"]]
    summary = {
        "chain": chain.key,
        "chain_id": chain.chain_id,
        "blockscout_pages": pages,
        "nft_contracts_discovered": len(contracts),
        "nft_contracts_inspected": len(rows),
        "nft_instances_sampled": sum(row["instances_sampled"] for row in rows),
        "contracts_with_model_candidates": sum(bool(row["model_candidates"]) for row in rows),
        "model_candidates": len(validations),
        "contracts_with_validated_vrms": sum(bool(row["validated_vrms"]) for row in rows),
        "validated_vrms": sum(len(row["validated_vrms"]) for row in rows),
        "validation_statuses": dict(Counter(str(item.get("status")) for item in validations)),
        "error_contracts": sum(bool(row["errors"]) for row in rows),
    }
    return {
        "schema": "blockscout-vrm-discovery-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chain": {
            "key": chain.key,
            "chain_id": chain.chain_id,
            "rpc": chain.rpc_urls[0],
            "explorer": chain.explorer_url,
            "blockscout_api": chain.blockscout_api,
        },
        "summary": summary,
        "contracts": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Discover VRM-bearing NFTs on a Blockscout-indexed EVM chain")
    ap.add_argument("--chain", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-contracts", type=int, default=250)
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--sample-instances", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args(argv)
    report = discover(args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
