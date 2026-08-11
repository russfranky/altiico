#!/usr/bin/env python3
"""High-recall OpenSea discovery for NFT collections that may expose VRM avatars.

OpenSea is a lead generator only. Token metadata is followed and scanned
recursively. A candidate is counted as VRM only after the referenced bytes pass
the catalog's GLB + VRM binary validator.
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

from scripts.opensea_client import OpenSeaClient  # noqa: E402
from scripts.crawler.fetch import NetworkLoader  # noqa: E402
from scripts.crawler.models import CrawlPolicy  # noqa: E402
from scripts.crawler.uri import canonicalize_uri  # noqa: E402
from scripts.discover_metadata_fields import scan_metadata  # noqa: E402
from scripts.discover_vrm_urls import fetch_metadata  # noqa: E402

DEFAULT_QUERIES = (
    "VRM", "VRM avatar", "3D avatar", "avatar 3D", "metaverse avatar",
    "GLB avatar", "glTF avatar", "PFP 3D", "avatar NFT",
    "collectible avatar", "digital avatar", "virtual avatar", "metaverse ready",
)
MODEL_EXTENSIONS = (".vrm", ".glb", ".gltf", ".fbx", ".usdz")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _slug(row: dict[str, Any]) -> str:
    for key in ("collection", "collection_slug", "slug"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("slug") or value.get("collection")
            if nested:
                return str(nested).strip()
    return ""


def _contract(row: dict[str, Any]) -> str:
    for key in ("contract", "address", "contract_address"):
        value = row.get(key)
        if isinstance(value, str) and value.startswith("0x"):
            return value.lower()
        if isinstance(value, dict):
            address = value.get("address")
            if isinstance(address, str) and address.startswith("0x"):
                return address.lower()
    contracts = row.get("contracts")
    if isinstance(contracts, list):
        for item in contracts:
            if isinstance(item, dict):
                address = item.get("address")
                if isinstance(address, str) and address.startswith("0x"):
                    return address.lower()
    return ""


def _candidate_score(row: dict[str, Any], query: str) -> int:
    blob = " ".join(_text(row.get(k)) for k in ("name", "description", "collection", "slug")).lower()
    score = 1
    if "vrm" in blob:
        score += 8
    if "avatar" in blob:
        score += 5
    if "3d" in blob or "3-d" in blob:
        score += 3
    if "metaverse" in blob:
        score += 2
    if query.lower() in blob:
        score += 2
    return score


def _direct_candidates(nft: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for key in ("animation_url", "display_animation_url"):
        value = nft.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        lower = value.lower().split("?", 1)[0].split("#", 1)[0]
        if lower.endswith(MODEL_EXTENSIONS) or key == "animation_url":
            found.append({
                "path": f"opensea.{key}", "field": key, "url": value.strip(),
                "reason": "opensea_media",
            })
    return found


def _validate(url: str, timeout: float) -> dict[str, Any]:
    policy = CrawlPolicy(timeout=timeout, max_attempts=2, max_vrm_bytes=64 * 1024 * 1024)
    loader = NetworkLoader(None, policy)
    try:
        result = loader.validate_vrm(canonicalize_uri(url))
        return {
            "canonical_url": result.canonical_url,
            "transport_url": result.transport_url,
            "valid": bool(result.valid),
            "status": result.status,
            "vrm_spec": result.vrm_spec,
            "content_sha256": result.content_sha256,
            "bytes": result.observed_length or result.total_length,
            "error": result.error,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "canonical_url": url, "valid": False, "status": "validation_error",
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


def _inspect_nft(nft: dict[str, Any], timeout: float) -> dict[str, Any]:
    token_id = _text(nft.get("identifier") or nft.get("token_id"))
    metadata_url = _text(nft.get("metadata_url"))
    candidates = _direct_candidates(nft)
    metadata_error: str | None = None
    metadata_fetched = False

    if metadata_url:
        try:
            metadata = fetch_metadata(metadata_url, timeout=timeout)
            metadata_fetched = True
            if isinstance(metadata, (dict, list)):
                candidates.extend(scan_metadata(metadata))
        except Exception as exc:  # noqa: BLE001
            metadata_error = f"{type(exc).__name__}: {exc}"[:500]

    out_candidates: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = _text(candidate.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        record = {
            "field": _text(candidate.get("field")),
            "path": _text(candidate.get("path")),
            "reason": _text(candidate.get("reason")),
            "url": url,
            "metadata_url": metadata_url,
            "token_id": token_id,
        }
        out_candidates.append(record)
        validation = _validate(url, timeout)
        validation.update({
            "field": record["field"], "path": record["path"],
            "reason": record["reason"], "metadata_url": metadata_url,
            "token_id": token_id,
        })
        validations.append(validation)

    return {
        "token_id": token_id,
        "metadata_url": metadata_url,
        "metadata_fetched": metadata_fetched,
        "metadata_error": metadata_error,
        "candidates": out_candidates,
        "validations": validations,
    }


async def discover(args: argparse.Namespace) -> dict[str, Any]:
    client = OpenSeaClient(max_concurrency=2)
    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]
    leads: dict[str, dict[str, Any]] = {}
    search_requests = 0
    metadata_documents_fetched = 0
    metadata_fetch_errors = 0

    try:
        for query in queries:
            for chain in chains:
                try:
                    data = await client.search(query, chain=chain, asset_type="collection", limit=args.search_limit)
                    search_requests += 1
                except Exception as exc:  # noqa: BLE001
                    print(f"search failed query={query!r} chain={chain}: {exc}", file=sys.stderr)
                    continue
                rows = data.get("collections") or data.get("results") or data.get("items") or []
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    slug = _slug(row)
                    if not slug:
                        continue
                    item = leads.setdefault(slug, {
                        "slug": slug, "name": _text(row.get("name")) or slug,
                        "description": _text(row.get("description")), "contract": _contract(row),
                        "queries": set(), "chains": set(), "score": 0,
                        "nfts_sampled": 0, "metadata_documents": 0,
                        "model_candidates": [], "validated_vrms": [],
                        "rejected_model_candidates": [], "errors": [],
                    })
                    item["queries"].add(query)
                    item["chains"].add(chain)
                    item["score"] = max(item["score"], _candidate_score(row, query))

        ranked = sorted(leads.values(), key=lambda x: (-x["score"], x["slug"]))[: args.max_collections]
        print(f"OpenSea search produced {len(leads)} unique collection leads; inspecting {len(ranked)}", file=sys.stderr)

        for idx, lead in enumerate(ranked, 1):
            try:
                data = await client.get_collection_nfts(lead["slug"], limit=args.sample)
                nfts = data.get("nfts") or []
            except Exception as exc:  # noqa: BLE001
                lead["errors"].append(f"collection_nfts: {type(exc).__name__}: {exc}"[:500])
                continue
            if not isinstance(nfts, list):
                continue
            nfts = [n for n in nfts if isinstance(n, dict)]
            lead["nfts_sampled"] = len(nfts)

            inspected = await asyncio.gather(*(
                asyncio.to_thread(_inspect_nft, nft, args.timeout) for nft in nfts
            ))
            seen_candidates: set[str] = set()
            seen_valid: set[str] = set()
            for result in inspected:
                if result["metadata_fetched"]:
                    metadata_documents_fetched += 1
                    lead["metadata_documents"] += 1
                if result["metadata_error"]:
                    metadata_fetch_errors += 1
                    lead["errors"].append(
                        f"metadata {result['token_id']}: {result['metadata_error']}"
                    )
                for candidate in result["candidates"]:
                    url = candidate["url"]
                    if url not in seen_candidates:
                        seen_candidates.add(url)
                        lead["model_candidates"].append(candidate)
                for validation in result["validations"]:
                    key = validation.get("canonical_url") or ""
                    if validation.get("valid"):
                        if key and key not in seen_valid:
                            seen_valid.add(key)
                            lead["validated_vrms"].append(validation)
                    else:
                        lead["rejected_model_candidates"].append(validation)
            if lead["validated_vrms"]:
                print(f"[{idx}/{len(ranked)}] VRM HIT {lead['name']} ({lead['slug']}): {len(lead['validated_vrms'])}", file=sys.stderr)
    finally:
        await client.close()

    ranked = sorted(leads.values(), key=lambda x: (-x["score"], x["slug"]))[: args.max_collections]
    for lead in ranked:
        lead["queries"] = sorted(lead["queries"])
        lead["chains"] = sorted(lead["chains"])
        lead["model_candidates"] = lead["model_candidates"][:200]
        lead["rejected_model_candidates"] = lead["rejected_model_candidates"][:200]

    valid = [v for x in ranked for v in x["validated_vrms"]]
    rejected = [v for x in ranked for v in x["rejected_model_candidates"]]
    summary = {
        "search_requests": search_requests,
        "queries": len(queries), "chains": len(chains),
        "unique_collection_leads": len(leads), "collections_inspected": len(ranked),
        "nfts_sampled": sum(x["nfts_sampled"] for x in ranked),
        "metadata_documents_fetched": metadata_documents_fetched,
        "metadata_fetch_errors": metadata_fetch_errors,
        "collections_with_model_candidates": sum(bool(x["model_candidates"]) for x in ranked),
        "model_candidates": sum(len(x["model_candidates"]) for x in ranked),
        "collections_with_validated_vrms": sum(bool(x["validated_vrms"]) for x in ranked),
        "validated_vrms": len(valid),
        "rejected_model_candidates": len(rejected),
        "error_collections": sum(bool(x["errors"]) for x in ranked),
        "validation_statuses": dict(Counter(v["status"] for v in [*valid, *rejected])),
    }
    return {
        "schema": "opensea-high-recall-discovery-v3",
        "generated_at": utc_now(), "summary": summary, "collections": ranked,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search OpenSea broadly for new VRM/avatar collection candidates.")
    ap.add_argument("--output", default=str(_REPO_ROOT / "data" / "opensea_discovery_report.json"))
    ap.add_argument("--queries", default=",".join(DEFAULT_QUERIES))
    ap.add_argument("--chains", default="ethereum,polygon,base,arbitrum,optimism")
    ap.add_argument("--search-limit", type=int, default=50)
    ap.add_argument("--sample", type=int, default=8)
    ap.add_argument("--max-collections", type=int, default=500)
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args(argv)

    if not os.getenv("OPENSEA_API_KEY") and not (Path.home() / ".opensea" / "api_key").exists():
        print("OpenSea credential missing: set OPENSEA_API_KEY or ~/.opensea/api_key", file=sys.stderr)
        return 2

    report = asyncio.run(discover(args))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
