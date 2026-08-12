#!/usr/bin/env python3
"""Census DickButtVerse numeric CDN asset IDs using structural VRM checks only.

This deliberately calls the numeric path component an *asset ID*, not an NFT
token ID. The current catalog has evidence that some Moralis token IDs match the
CDN filename, but this census does not generalize that identity mapping.

No avatar rows, collection supply values, or publication state are modified.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_dickbuttverse_inventory import (  # noqa: E402
    DEFAULT_DB,
    COLLECTION_ID,
    CONTRACT,
    URL_TEMPLATE,
    collection_supply,
    policy_for,
    structural_probe,
)

DEFAULT_OUT = ROOT / "data" / "dickbuttverse_inventory_census.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compress_ranges(values: list[int]) -> list[dict[str, int]]:
    if not values:
        return []
    ordered = sorted(set(values))
    ranges: list[dict[str, int]] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append({"start": start, "end": previous, "count": previous - start + 1})
        start = previous = value
    ranges.append({"start": start, "end": previous, "count": previous - start + 1})
    return ranges


def census(
    supply: int,
    *,
    workers: int,
    timeout: float,
    max_vrm_bytes: int,
) -> list[dict[str, Any]]:
    policy = policy_for(max_vrm_bytes, timeout)
    rows: list[dict[str, Any]] = []
    ids = list(range(supply))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(structural_probe, asset_id, policy): asset_id for asset_id in ids}
        completed = 0
        for future in as_completed(futures):
            row = future.result()
            row["assetId"] = row.pop("tokenId")
            rows.append(row)
            completed += 1
            if completed % 500 == 0 or completed == supply:
                print(f"censused {completed}/{supply} numeric CDN asset IDs", file=sys.stderr)
    return sorted(rows, key=lambda row: int(row["assetId"]))


def summarize(rows: list[dict[str, Any]], supply: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    structural_ids: list[int] = []
    missing_ids: list[int] = []
    other_ids: list[int] = []
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        asset_id = int(row["assetId"])
        if status == "structural_vrm":
            structural_ids.append(asset_id)
        elif row.get("errorClass") == "http_404":
            missing_ids.append(asset_id)
        else:
            other_ids.append(asset_id)
    return {
        "catalogSupplyReference": supply,
        "assetIdsCensused": len(rows),
        "statusCounts": dict(sorted(counts.items())),
        "structuralVrmAssets": len(structural_ids),
        "structuralVrmRate": round(len(structural_ids) / len(rows), 6) if rows else 0,
        "firstStructuralVrmAssetId": min(structural_ids) if structural_ids else None,
        "lastStructuralVrmAssetId": max(structural_ids) if structural_ids else None,
        "missing404Assets": len(missing_ids),
        "missing404Ranges": compress_ranges(missing_ids),
        "otherErrorAssets": len(other_ids),
        "otherErrorRanges": compress_ranges(other_ids),
        "structuralVrmRanges": compress_ranges(structural_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-vrm-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()

    supply = collection_supply(args.db)
    rows = census(
        supply,
        workers=args.workers,
        timeout=args.timeout,
        max_vrm_bytes=args.max_vrm_bytes,
    )
    payload = {
        "schema": "dickbuttverse-inventory-census-v1",
        "generatedAt": now_iso(),
        "collection": {
            "catalogId": COLLECTION_ID,
            "chain": "ethereum",
            "contract": CONTRACT,
            "catalogSupplyReference": supply,
            "urlTemplate": URL_TEMPLATE,
        },
        "policy": (
            "numeric CDN asset-ID coverage only; structural VRM checks are not whole-file "
            "promotion proof and asset IDs are not asserted to equal NFT token IDs"
        ),
        "summary": summarize(rows, supply),
        "assets": rows,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
