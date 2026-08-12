#!/usr/bin/env python3
"""Measure DickButtVerse VRM-template coverage without claiming full inventory.

The catalog has multiple binary-proven VRMs at a stable CDN template. This
script samples the full reported token range in two tiers:

1. structural probe: fetch only the GLB header + JSON chunk and require a
   VRM/VRMC_vrm extension;
2. full proof subset: run the existing complete-binary validator and whole-file
   SHA-256 on a smaller out-of-sample subset.

The output is discovery evidence only. It never creates avatar rows or marks a
collection bulk-ready.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import struct
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.crawler.fetch import GLB_MAGIC, GLB_VERSION_2, JSON_CHUNK_TYPE, NetworkLoader  # noqa: E402
from scripts.crawler.models import CrawlPolicy, PermanentCrawlError, RetryableCrawlError  # noqa: E402

COLLECTION_ID = "dickbuttverse"
CONTRACT = "0xd47d8672e45a7204057baaa3622a3fa276d651e3"
URL_TEMPLATE = "https://small.deccdn.com/paths/dbvTour/3dassets/assets/sept30/vrm/{token_id}.vrm"
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_OUT = ROOT / "data" / "dickbuttverse_inventory_probe.json"
DEFAULT_RECONCILIATION = ROOT / "data" / "moralis_candidate_reconciliation.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def collection_supply(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM collections WHERE id=?", (COLLECTION_ID,)
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError(f"missing catalog collection {COLLECTION_ID}")
    if str(row["chain"] or "").lower() != "ethereum":
        raise RuntimeError("DickButtVerse chain identity changed")
    if str(row["contract"] or "").lower() != CONTRACT:
        raise RuntimeError("DickButtVerse primary contract identity changed")
    for key in ("total_supply", "max_supply", "avatar_count"):
        if key not in row.keys():
            continue
        value = row[key]
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    raise RuntimeError("DickButtVerse has no positive catalog supply")


def known_proven_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids: set[int] = set()
    for row in payload.get("reconciled") or []:
        if not isinstance(row, dict) or row.get("catalogId") != COLLECTION_ID:
            continue
        try:
            ids.add(int(str(row.get("tokenId"))))
        except (TypeError, ValueError):
            continue
    return ids


def select_probe_ids(supply: int, sample_size: int, *, seed: int = 20260812) -> list[int]:
    if supply <= 0:
        return []
    sample_size = min(max(1, sample_size), supply)
    anchors = {0, supply - 1}
    for value in (1, 2, 10, 100, 999, 1000):
        if 0 <= value < supply:
            anchors.add(value)
    if sample_size > 1:
        for index in range(sample_size):
            anchors.add(round(index * (supply - 1) / (sample_size - 1)))
    rng = random.Random(seed)
    while len(anchors) < sample_size:
        anchors.add(rng.randrange(supply))
    if len(anchors) > sample_size:
        must_keep = {0, supply - 1}
        remaining = sorted(anchors - must_keep)
        rng.shuffle(remaining)
        anchors = must_keep | set(remaining[: sample_size - len(must_keep)])
    return sorted(anchors)


def select_full_ids(
    structural_ids: list[int], known_ids: set[int], full_sample_size: int, *, seed: int = 424242
) -> list[int]:
    candidates = [value for value in structural_ids if value not in known_ids]
    if not candidates:
        candidates = list(structural_ids)
    count = min(max(0, full_sample_size), len(candidates))
    if count == len(candidates):
        return sorted(candidates)
    rng = random.Random(seed)
    return sorted(rng.sample(candidates, count))


def url_for(token_id: int) -> str:
    return URL_TEMPLATE.format(token_id=token_id)


def policy_for(max_vrm_bytes: int, timeout: float) -> CrawlPolicy:
    return CrawlPolicy(
        max_depth=0,
        request_budget=32,
        max_tasks=8,
        max_attempts=1,
        timeout=timeout,
        max_document_bytes=2_000_000,
        max_vrm_json_bytes=4_000_000,
        max_vrm_bytes=max_vrm_bytes,
        max_links_per_document=0,
    )


def structural_probe(token_id: int, policy: CrawlPolicy) -> dict[str, Any]:
    url = url_for(token_id)
    loader = NetworkLoader(None, policy)
    requests = 0
    try:
        header_result = loader.fetch_range(url, 0, 19)
        requests += header_result.network_requests
        header = header_result.body
        if len(header) < 20:
            return {"tokenId": token_id, "url": url, "status": "invalid_glb", "requests": requests, "error": "header_too_short"}
        magic, version, total_length = struct.unpack("<III", header[:12])
        json_length, chunk_type = struct.unpack("<II", header[12:20])
        if magic != GLB_MAGIC or version != GLB_VERSION_2 or chunk_type != JSON_CHUNK_TYPE:
            return {"tokenId": token_id, "url": url, "status": "not_glb", "requests": requests, "totalLength": total_length}
        if total_length < 20 or total_length > policy.max_vrm_bytes:
            return {"tokenId": token_id, "url": url, "status": "invalid_glb", "requests": requests, "totalLength": total_length, "error": "declared_length_out_of_policy"}
        if json_length <= 0 or json_length > policy.max_vrm_json_bytes or 20 + json_length > total_length:
            return {"tokenId": token_id, "url": url, "status": "invalid_glb", "requests": requests, "totalLength": total_length, "error": "json_chunk_out_of_policy"}
        json_result = loader.fetch_range(
            url,
            20,
            20 + json_length - 1,
            preferred_transport=header_result.final_url,
        )
        requests += json_result.network_requests
        json_bytes = json_result.body
        gltf = json.loads(json_bytes.decode("utf-8").rstrip("\x00 \t\r\n"))
        extensions = gltf.get("extensions") if isinstance(gltf, dict) else None
        vrm_spec = None
        if isinstance(extensions, dict) and isinstance(extensions.get("VRMC_vrm"), dict):
            vrm_spec = "1.0"
        elif isinstance(extensions, dict) and isinstance(extensions.get("VRM"), dict):
            vrm_spec = "0.x"
        status = "structural_vrm" if vrm_spec else "valid_glb_not_vrm"
        return {
            "tokenId": token_id,
            "url": url,
            "status": status,
            "vrmSpec": vrm_spec,
            "totalLength": total_length,
            "jsonChunkSha256": hashlib.sha256(json_bytes).hexdigest(),
            "transportUrl": json_result.final_url,
            "requests": requests,
        }
    except RetryableCrawlError as exc:
        return {"tokenId": token_id, "url": url, "status": "transport_error", "requests": requests + exc.request_count, "errorClass": exc.error_class, "error": str(exc)}
    except PermanentCrawlError as exc:
        return {"tokenId": token_id, "url": url, "status": "permanent_error", "requests": requests + exc.request_count, "errorClass": exc.error_class, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"tokenId": token_id, "url": url, "status": "probe_error", "requests": requests, "errorClass": type(exc).__name__, "error": str(exc)}


def full_validate(token_id: int, policy: CrawlPolicy) -> dict[str, Any]:
    url = url_for(token_id)
    loader = NetworkLoader(None, policy)
    try:
        validation = asdict(loader.validate_vrm(url))
        return {
            "tokenId": token_id,
            "url": url,
            "status": validation.get("status"),
            "vrmSpec": validation.get("vrm_spec"),
            "sha256": validation.get("content_sha256") or None,
            "byteLength": validation.get("observed_length"),
            "transportUrl": validation.get("transport_url"),
            "requests": validation.get("network_requests"),
            "error": validation.get("error") or None,
        }
    except (RetryableCrawlError, PermanentCrawlError) as exc:
        return {"tokenId": token_id, "url": url, "status": "transport_error", "requests": exc.request_count, "errorClass": exc.error_class, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"tokenId": token_id, "url": url, "status": "validation_error", "requests": 0, "errorClass": type(exc).__name__, "error": str(exc)}


def run_parallel(ids: list[int], fn, policy: CrawlPolicy, workers: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fn, token_id, policy): token_id for token_id in ids}
        for future in as_completed(futures):
            rows.append(future.result())
    return sorted(rows, key=lambda row: int(row["tokenId"]))


def counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    output: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        output[status] = output.get(status, 0) + 1
    return dict(sorted(output.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample-size", type=int, default=96)
    parser.add_argument("--full-sample-size", type=int, default=24)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-vrm-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()

    supply = collection_supply(args.db)
    known_ids = known_proven_ids(args.reconciliation)
    probe_ids = select_probe_ids(supply, args.sample_size)
    policy = policy_for(args.max_vrm_bytes, args.timeout)
    structural = run_parallel(probe_ids, structural_probe, policy, args.workers)
    structural_valid_ids = [int(row["tokenId"]) for row in structural if row.get("status") == "structural_vrm"]
    full_ids = select_full_ids(structural_valid_ids, known_ids, args.full_sample_size)
    full = run_parallel(full_ids, full_validate, policy, min(args.workers, 4))

    structural_counts = counts(structural)
    full_counts = counts(full)
    payload = {
        "schema": "dickbuttverse-inventory-probe-v1",
        "generatedAt": now_iso(),
        "collection": {
            "catalogId": COLLECTION_ID,
            "chain": "ethereum",
            "contract": CONTRACT,
            "catalogSupply": supply,
            "urlTemplate": URL_TEMPLATE,
        },
        "policy": "bounded coverage measurement only; structural checks are not promotion proof and sampled full validation does not establish complete inventory",
        "summary": {
            "knownBinaryProofsBeforeProbe": len(known_ids),
            "structuralSampleSize": len(structural),
            "structuralStatusCounts": structural_counts,
            "structuralVrmRate": round(structural_counts.get("structural_vrm", 0) / len(structural), 6) if structural else 0,
            "fullValidationSampleSize": len(full),
            "fullValidationStatusCounts": full_counts,
            "fullValidVrmRate": round(full_counts.get("valid_vrm", 0) / len(full), 6) if full else 0,
            "fullValidatedBytes": sum(int(row.get("byteLength") or 0) for row in full if row.get("status") == "valid_vrm"),
        },
        "knownProvenIds": sorted(known_ids),
        "structuralProbe": structural,
        "fullValidation": full,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
