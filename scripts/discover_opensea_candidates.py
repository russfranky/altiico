#!/usr/bin/env python3
"""High-recall OpenSea discovery for NFT collections that may expose VRM avatars.

OpenSea is used only to generate and enrich leads. Nothing discovered here is
promoted into the canonical catalog until the referenced bytes pass GLB + VRM
validation through the recursive crawler.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
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

DEFAULT_QUERIES = (
    "VRM",
    "VRM avatar",
    "3D avatar",
    "avatar 3D",
    "metaverse avatar",
    "GLB avatar",
    "glTF avatar",
    "PFP 3D",
    "avatar NFT",
    "collectible avatar",
    "digital avatar",
    "virtual avatar",
    "metaverse ready",
)

MODEL_EXTENSIONS = (".vrm", ".glb", ".gltf", ".fbx", ".usdz")
STRONG_TERMS = ("vrm", "avatar", "metaverse", "3d", "gltf", "glb")


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
    blob = " ".join(
        _text(row.get(k)) for k in ("name", "description", "collection", "slug")
    ).lower()
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


def _model_candidates(nft: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for key in ("animation_url", "metadata_url", "display_animation_url", "external_url"):
        value = nft.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        lower = value.lower().split("?", 1)[0]
        if key == "animation_url" or lower.endswith(MODEL_EXTENSIONS) or any(t in lower for t in ("vrm", "gltf", "glb")):
            found.append({"field": key, "url": value.strip()})
    return found


def _validate_vrm(url: str, loader: NetworkLoader) -> dict[str, Any]:
    try:
        canonical = canonicalize_uri(url)
        result = loader.validate_vrm(canonical)
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
        return {"canonical_url": url, "valid": False, "status": "validation_error", "error": f"{type(exc).__name__}: {exc}"[:500]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search OpenSea broadly for new VRM/avatar collection candidates.")
    ap.add_argument("--output", default=str(_REPO_ROOT / "data" / "opensea_discovery_report.json"))
    ap.add_argument("--queries", default=",".join(DEFAULT_QUERIES))
    ap.add_argument("--chains", default="ethereum,polygon,base,arbitrum,optimism")
    ap.add_argument("--search-limit", type=int, default=50)
    ap.add_argument("--sample", type=int, default=8, help="NFTs sampled per collection")
    ap.add_argument("--max-collections", type=int, default=500)
    ap.add_argument("--timeout", type=float, default=18.0)
    args = ap.parse_args(argv)

    if not os.getenv("OPENSEA_API_KEY") and not (Path.home() / ".opensea" / "api_key").exists():
        print("OpenSea credential missing: set OPENSEA_API_KEY or ~/.opensea/api_key", file=sys.stderr)
        return 2

    client = OpenSeaClient(timeout=args.timeout)
    policy = CrawlPolicy(timeout=args.timeout, max_attempts=2, max_vrm_bytes=64 * 1024 * 1024)
    loader = NetworkLoader(None, policy)
    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]

    leads: dict[str, dict[str, Any]] = {}
    search_requests = 0
    for query in queries:
        for chain in chains:
            try:
                data = client.request_json(
                    "/search",
                    params={"query": query, "chains": chain, "asset_types": "collection", "limit": min(args.search_limit, 50)},
                )
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
                    "slug": slug,
                    "name": _text(row.get("name")) or slug,
                    "description": _text(row.get("description")),
                    "contract": _contract(row),
                    "queries": set(),
                    "chains": set(),
                    "score": 0,
                    "nfts_sampled": 0,
                    "model_candidates": [],
                    "validated_vrms": [],
                    "errors": [],
                })
                item["queries"].add(query)
                item["chains"].add(chain)
                item["score"] = max(item["score"], _candidate_score(row, query))

    ranked = sorted(leads.values(), key=lambda x: (-x["score"], x["slug"]))[: args.max_collections]
    print(f"OpenSea search produced {len(leads)} unique collection leads; inspecting {len(ranked)}", file=sys.stderr)

    for idx, lead in enumerate(ranked, 1):
        slug = lead["slug"]
        try:
            data = client.request_json(f"/collection/{urllib.parse.quote(slug, safe='')}/nfts", params={"limit": min(args.sample, 50)})
            nfts = data.get("nfts") or []
        except Exception as exc:  # noqa: BLE001
            lead["errors"].append(f"collection_nfts: {type(exc).__name__}: {exc}"[:500])
            continue
        if not isinstance(nfts, list):
            continue
        lead["nfts_sampled"] = len(nfts)
        seen_urls: set[str] = set()
        for nft in nfts:
            if not isinstance(nft, dict):
                continue
            for candidate in _model_candidates(nft):
                url = candidate["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                record = {**candidate, "token_id": _text(nft.get("identifier") or nft.get("token_id"))}
                lead["model_candidates"].append(record)
                if ".vrm" in url.lower() or "vrm" in candidate["field"].lower():
                    validation = _validate_vrm(url, loader)
                    validation.update({"field": candidate["field"], "token_id": record["token_id"]})
                    if validation.get("valid"):
                        lead["validated_vrms"].append(validation)
        if lead["validated_vrms"]:
            print(f"[{idx}/{len(ranked)}] VRM HIT {lead['name']} ({slug}): {len(lead['validated_vrms'])}", file=sys.stderr)

    for lead in ranked:
        lead["queries"] = sorted(lead["queries"])
        lead["chains"] = sorted(lead["chains"])
        lead["model_candidates"] = lead["model_candidates"][:100]

    summary = {
        "search_requests": search_requests,
        "queries": len(queries),
        "chains": len(chains),
        "unique_collection_leads": len(leads),
        "collections_inspected": len(ranked),
        "nfts_sampled": sum(x["nfts_sampled"] for x in ranked),
        "collections_with_model_candidates": sum(bool(x["model_candidates"]) for x in ranked),
        "model_candidates": sum(len(x["model_candidates"]) for x in ranked),
        "collections_with_validated_vrms": sum(bool(x["validated_vrms"]) for x in ranked),
        "validated_vrms": sum(len(x["validated_vrms"]) for x in ranked),
        "error_collections": sum(bool(x["errors"]) for x in ranked),
        "validation_statuses": dict(Counter(v["status"] for x in ranked for v in x["validated_vrms"])),
    }
    report = {
        "schema": "opensea-high-recall-discovery-v1",
        "generated_at": utc_now(),
        "summary": summary,
        "collections": ranked,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
