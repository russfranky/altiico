#!/usr/bin/env python3
"""Census DickButtVerse numeric CDN asset IDs using structural VRM checks only.

This deliberately calls the numeric path component an *asset ID*, not an NFT
token ID. The current catalog has evidence that some Moralis token IDs match the
CDN filename, but this census does not generalize that identity mapping.

The census is resumable. Previously confirmed structural/permanent observations
are retained, while transport failures are retried with pacing and bounded
backoff so CDN throttling cannot be mistaken for missing assets.

No avatar rows, collection supply values, or publication state are modified.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import Counter
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
RETRYABLE_STATUSES = {"transport_error", "probe_error"}


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


class PaceGate:
    def __init__(self, interval_seconds: float) -> None:
        self.interval = max(0.0, float(interval_seconds))
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if delay:
            time.sleep(delay)


def reusable_previous_rows(output: Path, supply: int) -> dict[int, dict[str, Any]]:
    if not output.exists():
        return {}
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if payload.get("schema") != "dickbuttverse-inventory-census-v1":
        return {}
    collection = payload.get("collection") or {}
    if collection.get("catalogId") != COLLECTION_ID or collection.get("catalogSupplyReference") != supply:
        return {}
    out: dict[int, dict[str, Any]] = {}
    for row in payload.get("assets") or []:
        if not isinstance(row, dict):
            continue
        try:
            asset_id = int(row.get("assetId"))
        except (TypeError, ValueError):
            continue
        if 0 <= asset_id < supply and str(row.get("status") or "") not in RETRYABLE_STATUSES:
            out[asset_id] = row
    return out


def paced_probe(
    asset_id: int,
    policy,
    gate: PaceGate,
    attempts: int,
) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for attempt in range(1, max(1, attempts) + 1):
        gate.wait()
        row = structural_probe(asset_id, policy)
        row["assetId"] = row.pop("tokenId")
        row["attempts"] = attempt
        last = row
        if row.get("status") not in RETRYABLE_STATUSES:
            return row
        if attempt < attempts:
            time.sleep(min(8.0, float(2 ** (attempt - 1))))
    assert last is not None
    return last


def census(
    supply: int,
    *,
    workers: int,
    timeout: float,
    max_vrm_bytes: int,
    previous_rows: dict[int, dict[str, Any]] | None = None,
    attempts: int = 3,
    pace_seconds: float = 0.5,
) -> list[dict[str, Any]]:
    policy = policy_for(max_vrm_bytes, timeout)
    by_id = dict(previous_rows or {})
    unresolved = [asset_id for asset_id in range(supply) if asset_id not in by_id]
    gate = PaceGate(pace_seconds)
    print(
        f"reusing {len(by_id)} settled observations; retrying {len(unresolved)} asset IDs",
        file=sys.stderr,
    )
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(paced_probe, asset_id, policy, gate, attempts): asset_id
            for asset_id in unresolved
        }
        completed = 0
        for future in as_completed(futures):
            row = future.result()
            by_id[int(row["assetId"])] = row
            completed += 1
            if completed % 250 == 0 or completed == len(unresolved):
                print(f"retried {completed}/{len(unresolved)} unresolved asset IDs", file=sys.stderr)
    return [by_id[asset_id] for asset_id in range(supply)]


def summarize(rows: list[dict[str, Any]], supply: int) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    error_classes: Counter[str] = Counter()
    structural_ids: list[int] = []
    missing_ids: list[int] = []
    other_ids: list[int] = []
    retryable_ids: list[int] = []
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] += 1
        error_class = str(row.get("errorClass") or "")
        if error_class:
            error_classes[error_class] += 1
        asset_id = int(row["assetId"])
        if status == "structural_vrm":
            structural_ids.append(asset_id)
        elif error_class == "http_404":
            missing_ids.append(asset_id)
        else:
            other_ids.append(asset_id)
            if status in RETRYABLE_STATUSES:
                retryable_ids.append(asset_id)
    return {
        "catalogSupplyReference": supply,
        "assetIdsCensused": len(rows),
        "statusCounts": dict(sorted(counts.items())),
        "errorClassCounts": dict(sorted(error_classes.items())),
        "structuralVrmAssets": len(structural_ids),
        "structuralVrmRate": round(len(structural_ids) / len(rows), 6) if rows else 0,
        "firstStructuralVrmAssetId": min(structural_ids) if structural_ids else None,
        "lastStructuralVrmAssetId": max(structural_ids) if structural_ids else None,
        "missing404Assets": len(missing_ids),
        "missing404Ranges": compress_ranges(missing_ids),
        "otherErrorAssets": len(other_ids),
        "otherErrorRanges": compress_ranges(other_ids),
        "retryableUnresolvedAssets": len(retryable_ids),
        "retryableUnresolvedRanges": compress_ranges(retryable_ids),
        "structuralVrmRanges": compress_ranges(structural_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-vrm-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--pace-seconds", type=float, default=0.5)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    supply = collection_supply(args.db)
    previous = {} if args.no_resume else reusable_previous_rows(args.output, supply)
    rows = census(
        supply,
        workers=args.workers,
        timeout=args.timeout,
        max_vrm_bytes=args.max_vrm_bytes,
        previous_rows=previous,
        attempts=args.attempts,
        pace_seconds=args.pace_seconds,
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
            "promotion proof and asset IDs are not asserted to equal NFT token IDs; "
            "transport failures are retried with pacing and are never treated as missing assets"
        ),
        "resume": {
            "settledRowsReused": len(previous),
            "rowsRetried": supply - len(previous),
            "attemptsPerRetriedAsset": args.attempts,
            "paceSecondsBetweenAssetStarts": args.pace_seconds,
            "workers": args.workers,
        },
        "summary": summarize(rows, supply),
        "assets": rows,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
