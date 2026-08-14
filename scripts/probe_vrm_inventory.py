#!/usr/bin/env python3
"""Range-probe every enumerated inventory URL for a real VRM extension.

This is the inventory-scale validator. It intentionally stops after the GLB
header and JSON chunk, proving that a link resolves to GLB 2.0 with `VRM` or
`VRMC_vrm` without downloading the complete binary for every token.

Whole-file SHA-256 remains required by the existing promotion validator before a
binary is treated as ingest-ready. This probe answers a different question:
"does every catalog inventory link actually point at a structurally valid VRM?"
"""
from __future__ import annotations

import argparse
import hashlib
import json
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

from scripts.crawler.fetch import (  # noqa: E402
    GLB_MAGIC,
    GLB_VERSION_2,
    JSON_CHUNK_TYPE,
    NetworkLoader,
)
from scripts.crawler.models import (  # noqa: E402
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
)

DEFAULT_SOURCE = ROOT / "data" / "moralis_full_vrm_inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "vrm_inventory_probe.json"
TERMINAL_STATES = {"not_shipped", "unrecoverable"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def probe_url(
    url: str,
    policy: CrawlPolicy,
    *,
    loader: NetworkLoader | None = None,
) -> dict[str, Any]:
    own_loader = loader or NetworkLoader(None, policy)  # type: ignore[arg-type]
    requests = 0
    try:
        header_result = own_loader.fetch_range(url, 0, 19)
        requests += int(header_result.network_requests or 0)
        header = header_result.body
        if len(header) < 20:
            return {
                "url": url,
                "status": "invalid_glb",
                "validVrm": False,
                "error": f"header too short: {len(header)}",
                "networkRequests": requests,
            }
        magic, version, total_length = struct.unpack("<III", header[:12])
        json_length, chunk_type = struct.unpack("<II", header[12:20])
        if magic != GLB_MAGIC or version != GLB_VERSION_2 or chunk_type != JSON_CHUNK_TYPE:
            return {
                "url": url,
                "status": "not_glb",
                "validVrm": False,
                "error": "not GLB 2.0 with a JSON first chunk",
                "networkRequests": requests,
            }
        if total_length < 20 or total_length > policy.max_vrm_bytes:
            return {
                "url": url,
                "status": "invalid_glb",
                "validVrm": False,
                "totalLength": total_length,
                "error": "declared GLB length outside policy",
                "networkRequests": requests,
            }
        if json_length <= 0 or json_length > policy.max_vrm_json_bytes:
            return {
                "url": url,
                "status": "invalid_glb",
                "validVrm": False,
                "totalLength": total_length,
                "error": "JSON chunk length outside policy",
                "networkRequests": requests,
            }
        if 20 + json_length > total_length:
            return {
                "url": url,
                "status": "invalid_glb",
                "validVrm": False,
                "totalLength": total_length,
                "error": "JSON chunk exceeds declared GLB length",
                "networkRequests": requests,
            }

        json_result = own_loader.fetch_range(
            url,
            20,
            20 + json_length - 1,
            preferred_transport=header_result.final_url,
        )
        requests += int(json_result.network_requests or 0)
        json_bytes = json_result.body
        json_sha = hashlib.sha256(json_bytes).hexdigest()
        try:
            gltf = json.loads(json_bytes.decode("utf-8").rstrip("\x00 \t\r\n"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {
                "url": url,
                "status": "invalid_glb",
                "validVrm": False,
                "totalLength": total_length,
                "jsonChunkSha256": json_sha,
                "error": f"invalid GLB JSON: {exc}",
                "networkRequests": requests,
            }
        extensions = gltf.get("extensions") if isinstance(gltf, dict) else None
        if not isinstance(extensions, dict):
            return {
                "url": url,
                "status": "valid_glb_not_vrm",
                "validVrm": False,
                "totalLength": total_length,
                "jsonChunkSha256": json_sha,
                "error": "GLB has no extensions object",
                "networkRequests": requests,
            }
        if isinstance(extensions.get("VRMC_vrm"), dict):
            spec = "1.0"
        elif isinstance(extensions.get("VRM"), dict):
            spec = "0.x"
        else:
            return {
                "url": url,
                "status": "valid_glb_not_vrm",
                "validVrm": False,
                "totalLength": total_length,
                "jsonChunkSha256": json_sha,
                "error": "GLB has no VRM or VRMC_vrm extension",
                "networkRequests": requests,
            }
        return {
            "url": url,
            "status": "valid_vrm",
            "validVrm": True,
            "vrmSpec": spec,
            "totalLength": total_length,
            "jsonChunkSha256": json_sha,
            "networkRequests": requests,
            "transportUrl": json_result.final_url,
            "error": None,
        }
    except RetryableCrawlError as exc:
        requests += int(exc.request_count or 0)
        return {
            "url": url,
            "status": "transport_error",
            "validVrm": False,
            "retryable": True,
            "errorClass": exc.error_class,
            "error": str(exc),
            "networkRequests": requests,
        }
    except PermanentCrawlError as exc:
        requests += int(exc.request_count or 0)
        return {
            "url": url,
            "status": "transport_error",
            "validVrm": False,
            "retryable": False,
            "errorClass": exc.error_class,
            "error": str(exc),
            "networkRequests": requests,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "status": "internal_error",
            "validVrm": False,
            "error": f"{type(exc).__name__}: {exc}",
            "networkRequests": requests,
        }


def collection_probe_summary(
    collection: dict[str, Any],
    probes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    terminal_state = str(collection.get("terminalResearchState") or "").strip().lower()
    urls = sorted({str(url) for url in collection.get("vrmUrls") or [] if url})
    if terminal_state in TERMINAL_STATES:
        return {
            "catalogId": collection.get("catalogId"),
            "name": collection.get("name"),
            "terminalResearchState": terminal_state,
            "metadataComplete": bool(collection.get("metadataComplete")),
            "structurallyComplete": bool(collection.get("metadataComplete")),
            "urls": 0,
            "validVrmUrls": 0,
            "invalidUrls": [],
        }

    invalid = [url for url in urls if not (probes.get(url) or {}).get("validVrm")]
    metadata_complete = bool(collection.get("metadataComplete"))
    return {
        "catalogId": collection.get("catalogId"),
        "name": collection.get("name"),
        "terminalResearchState": None,
        "metadataComplete": metadata_complete,
        "structurallyComplete": bool(metadata_complete and urls and not invalid),
        "urls": len(urls),
        "validVrmUrls": len(urls) - len(invalid),
        "invalidUrls": invalid,
    }


def run(
    source_path: Path,
    output_path: Path,
    *,
    workers: int = 4,
    timeout: float = 20.0,
) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    collections = [row for row in source.get("collections") or [] if isinstance(row, dict)]
    urls = sorted(
        {
            str(url)
            for collection in collections
            if str(collection.get("terminalResearchState") or "").lower() not in TERMINAL_STATES
            for url in collection.get("vrmUrls") or []
            if url
        }
    )
    policy = CrawlPolicy(
        max_depth=0,
        request_budget=max(2_000, len(urls) * 4),
        max_tasks=max(20_000, len(urls) * 2),
        max_attempts=2,
        timeout=timeout,
        max_document_bytes=2_000_000,
        max_vrm_json_bytes=4_000_000,
        max_vrm_bytes=64 * 1024 * 1024,
        max_links_per_document=0,
    )

    probed: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(probe_url, url, policy): url for url in urls}
        completed = 0
        for future in as_completed(futures):
            url = futures[future]
            probed[url] = future.result()
            completed += 1
            if completed % 100 == 0 or completed == len(urls):
                print(f"probed {completed}/{len(urls)} inventory VRM URLs", file=sys.stderr)

    collection_results = [collection_probe_summary(row, probed) for row in collections]
    status_counts: dict[str, int] = {}
    for result in probed.values():
        status = str(result.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    payload = {
        "schema": "vrm-inventory-structural-probe-v1",
        "generatedAt": now_iso(),
        "sourceGeneratedAt": source.get("generatedAt"),
        "policy": (
            "Every enumerated non-terminal inventory URL must range-probe as GLB 2.0 with VRM/VRMC_vrm; "
            "whole-file hash remains a separate promotion requirement."
        ),
        "summary": {
            "collections": len(collection_results),
            "structurallyCompleteCollections": sum(
                bool(row.get("structurallyComplete")) for row in collection_results
            ),
            "urls": len(urls),
            "validVrmUrls": sum(bool(row.get("validVrm")) for row in probed.values()),
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "collections": collection_results,
        "probes": [probed[url] for url in urls],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = run(args.source, args.output, workers=args.workers, timeout=args.timeout)
    print(json.dumps(payload["summary"], indent=2))
    if args.strict and payload["summary"]["structurallyCompleteCollections"] != payload["summary"]["collections"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
