#!/usr/bin/env python3
"""Build compact source consensus without hiding disagreements.

Immutable identity stays anchored to catalog/discovery evidence. Mutable fields
are represented as source-stamped observations, with a preferred value only when
sources agree or one source is missing. Conflicts remain explicit review items.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = ROOT / "data" / "source_cross_reference_report.json"
DEFAULT_OUT = ROOT / "data" / "source_consensus.json"


def text(v: Any) -> str | None:
    s = str(v or "").strip()
    return s or None


def pick(comparisons: list[dict[str, Any]], field: str) -> dict[str, Any]:
    c = next((x for x in comparisons if x.get("field") == field), None)
    if not c:
        return {"preferred": None, "status": "unobserved", "sources": {}}
    a, b, agrees = c.get("catalogOrOpenSea"), c.get("moralis"), c.get("agrees")
    sources = {"catalogOrOpenSea": a, "moralis": b}
    if agrees is True:
        return {"preferred": a if a not in (None, "") else b, "status": "corroborated", "sources": sources}
    if agrees is False:
        return {"preferred": None, "status": "conflict", "sources": sources}
    if a not in (None, ""):
        return {"preferred": a, "status": "single_source_catalog_or_opensea", "sources": sources}
    if b not in (None, ""):
        return {"preferred": b, "status": "single_source_moralis", "sources": sources}
    return {"preferred": None, "status": "unobserved", "sources": sources}


def build(report: dict[str, Any]) -> dict[str, Any]:
    collections: dict[str, Any] = {}
    review: list[dict[str, Any]] = []
    for item in report.get("collections") or []:
        cid = item.get("catalogId")
        if not cid:
            continue
        comparisons = item.get("comparisons") or []
        media = {
            "banner": pick(comparisons, "banner_image_url"),
            "image": pick(comparisons, "image_url"),
        }
        stats = {
            "totalSupply": pick(comparisons, "total_supply"),
            "owners": pick(comparisons, "num_owners"),
            "floorPrice": pick(comparisons, "floor_price"),
        }
        name = pick(comparisons, "name")
        moralis = item.get("moralis") or {}
        meta = moralis.get("metadata") or {}
        entry = {
            "catalogId": cid,
            "identity": {
                "chain": item.get("chain"),
                "contract": item.get("contract"),
                "canonicalName": item.get("name"),
                "nameObservation": name,
                "policy": "chain+contract remain anchored to validated catalog/discovery evidence; indexer names are aliases/corroboration only",
            },
            "media": media,
            "stats": stats,
            "moralisSignals": {
                "verifiedCollection": meta.get("verified_collection"),
                "possibleSpam": meta.get("possible_spam"),
                "syncedAt": meta.get("synced_at"),
                "transferCount": ((moralis.get("stats") or {}).get("transfers") or {}).get("total"),
                "sampledNfts": moralis.get("sampledNfts") or [],
            },
            "observedAt": item.get("observedAt"),
            "errors": item.get("errors") or [],
        }
        collections[cid] = entry
        conflict_fields = [
            name_key
            for name_key, value in (
                ("name", name),
                ("banner", media["banner"]),
                ("image", media["image"]),
                ("totalSupply", stats["totalSupply"]),
                ("owners", stats["owners"]),
                ("floorPrice", stats["floorPrice"]),
            )
            if value.get("status") == "conflict"
        ]
        if conflict_fields or entry["errors"]:
            review.append({
                "catalogId": cid,
                "name": item.get("name"),
                "chain": item.get("chain"),
                "contract": item.get("contract"),
                "conflictFields": conflict_fields,
                "errors": entry["errors"],
            })
    status_counts: dict[str, int] = {}
    for entry in collections.values():
        for value in [entry["identity"]["nameObservation"], *entry["media"].values(), *entry["stats"].values()]:
            status = value.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema": "catalog-source-consensus-v1",
        "generatedAt": report.get("generatedAt"),
        "sourceReport": "data/source_cross_reference_report.json",
        "policy": report.get("policy") or {},
        "summary": {
            "collections": len(collections),
            "reviewItems": len(review),
            "observationStatusCounts": status_counts,
        },
        "reviewQueue": review,
        "collections": collections,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    consensus = build(report)
    Path(args.output).write_text(json.dumps(consensus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(consensus["summary"], indent=2))
    print(json.dumps(consensus["reviewQueue"][:20], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
