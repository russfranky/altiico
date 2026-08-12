#!/usr/bin/env python3
"""Binary-validate high-signal Moralis model candidates from deferred collections.

Moralis model discovery is intentionally lead-only. This pass reuses the
catalog's existing NetworkLoader.validate_vrm() gate and emits promotion-ready
records only when a complete GLB 2.0 binary contains VRM/VRMC_vrm and has a
whole-file SHA-256.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.crawler.fetch import NetworkLoader  # noqa: E402
from scripts.crawler.models import (  # noqa: E402
    CrawlPolicy,
    PermanentCrawlError,
    RetryableCrawlError,
)
from scripts.crawler.uri import canonicalize_uri  # noqa: E402

DEFAULT_SOURCE = ROOT / "data" / "moralis_model_discovery.json"
DEFAULT_STAGING = ROOT / "static" / "data" / "hubzz-prealpha-staging.json"
DEFAULT_OUTPUT = ROOT / "data" / "moralis_candidate_validation.json"
SUPPORTED_SUFFIXES = {".vrm", ".glb"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stageable_collection_ids(staging: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in staging.get("sets") or []:
        if not isinstance(item, dict):
            continue
        set_row = item.get("set") or {}
        slug = set_row.get("slug") if isinstance(set_row, dict) else None
        if slug:
            out.add(str(slug))
    return out


def candidate_suffix(url: str) -> str:
    path = urllib.parse.urlsplit(url).path.lower()
    for suffix in SUPPORTED_SUFFIXES:
        if path.endswith(suffix):
            return suffix
    return ""


def candidate_priority(url: str, unsupported_media: bool) -> tuple[int, str]:
    suffix = candidate_suffix(url)
    if suffix == ".vrm":
        rank = 0
    elif unsupported_media:
        rank = 1
    else:
        rank = 2
    return rank, url


def build_candidate_registry(
    report: dict[str, Any], skip_collections: set[str]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    registry: dict[str, dict[str, Any]] = {}
    skipped_existing = 0
    skipped_suffix = 0
    invalid_uri = 0
    bindings_seen = 0

    for collection in report.get("collections") or []:
        if not isinstance(collection, dict):
            continue
        catalog_id = str(collection.get("catalogId") or "").strip()
        if not catalog_id:
            continue
        if catalog_id in skip_collections:
            skipped_existing += 1
            continue
        for nft in collection.get("nfts") or []:
            if not isinstance(nft, dict):
                continue
            unsupported = bool(nft.get("unsupportedMedia"))
            token_id = str(nft.get("tokenId") or "").strip()
            for candidate in nft.get("modelCandidates") or []:
                if not isinstance(candidate, dict):
                    continue
                raw_url = str(candidate.get("url") or "").strip()
                if not raw_url or candidate_suffix(raw_url) not in SUPPORTED_SUFFIXES:
                    skipped_suffix += 1
                    continue
                try:
                    canonical = canonicalize_uri(raw_url)
                except (PermanentCrawlError, RetryableCrawlError):
                    invalid_uri += 1
                    continue
                bindings_seen += 1
                entry = registry.setdefault(
                    canonical,
                    {
                        "canonical_url": canonical,
                        "priority": candidate_priority(raw_url, unsupported),
                        "bindings": [],
                    },
                )
                entry["priority"] = min(
                    entry["priority"], candidate_priority(raw_url, unsupported)
                )
                binding = {
                    "catalogId": catalog_id,
                    "collectionId": catalog_id,
                    "name": collection.get("name"),
                    "chain": collection.get("chain"),
                    "contract": collection.get("contract"),
                    "tokenId": token_id or None,
                    "tokenUri": nft.get("tokenUri"),
                    "modelUrl": raw_url,
                    "sourcePath": candidate.get("path"),
                    "unsupportedMedia": unsupported,
                }
                identity = (
                    binding["catalogId"],
                    binding["tokenId"],
                    binding["modelUrl"],
                )
                if not any(
                    (b["catalogId"], b["tokenId"], b["modelUrl"]) == identity
                    for b in entry["bindings"]
                ):
                    entry["bindings"].append(binding)

    candidates = sorted(
        registry.values(), key=lambda row: (row["priority"], row["canonical_url"])
    )
    stats = {
        "uniqueCandidateUrls": len(candidates),
        "candidateBindings": bindings_seen,
        "skippedStageableCollections": skipped_existing,
        "skippedUnsupportedSuffixes": skipped_suffix,
        "invalidCandidateUris": invalid_uri,
    }
    return candidates, stats


def validate_candidate(
    candidate: dict[str, Any], policy: CrawlPolicy, max_attempts: int
) -> dict[str, Any]:
    canonical = str(candidate["canonical_url"])
    loader = NetworkLoader(None, policy)  # validate_vrm does not use the cache store
    errors: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        try:
            validation = asdict(loader.validate_vrm(canonical))
            validation["attempts"] = attempt
            validation["latency_seconds"] = round(time.monotonic() - started, 3)
            return {"candidate": candidate, "validation": validation, "errors": errors}
        except RetryableCrawlError as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "error_class": exc.error_class,
                    "error": str(exc),
                    "network_requests": exc.request_count,
                    "retryable": True,
                }
            )
            if attempt < max_attempts:
                delay = exc.retry_after if exc.retry_after is not None else 2 ** (attempt - 1)
                time.sleep(min(5.0, max(0.0, float(delay))))
        except PermanentCrawlError as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "error_class": exc.error_class,
                    "error": str(exc),
                    "network_requests": exc.request_count,
                    "retryable": False,
                }
            )
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "attempt": attempt,
                    "error_class": "internal_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "network_requests": 0,
                    "retryable": False,
                }
            )
            break
    return {"candidate": candidate, "validation": None, "errors": errors}


def expand_results(
    audited: list[dict[str, Any]], observed_at: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in audited:
        candidate = item["candidate"]
        validation = item.get("validation") or {}
        status = str(validation.get("status") or "transport_error")
        for binding in candidate.get("bindings") or []:
            row = {
                **binding,
                "source": "moralis_model_discovery",
                "observedAt": observed_at,
                "canonical_url": candidate["canonical_url"],
                "status": status,
                "validation_status": status,
                "vrm_spec": validation.get("vrm_spec"),
                "sha256": validation.get("content_sha256") or None,
                "byte_length": validation.get("observed_length"),
                "transport_url": validation.get("transport_url"),
                "json_chunk_sha256": validation.get("json_chunk_sha256") or None,
                "validation_error": validation.get("error") or None,
                "validation_attempts": validation.get("attempts"),
                "validation_errors": item.get("errors") or [],
            }
            out.append(row)
    return out


def summarize(
    results: list[dict[str, Any]], registry_stats: dict[str, int], attempted_urls: int
) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    valid_collections: set[str] = set()
    validated_bytes = 0
    for row in results:
        status = str(row.get("status") or "transport_error")
        statuses[status] = statuses.get(status, 0) + 1
        if status == "valid_vrm" and row.get("sha256") and row.get("vrm_spec"):
            if row.get("catalogId"):
                valid_collections.add(str(row["catalogId"]))
            validated_bytes += int(row.get("byte_length") or 0)
    return {
        **registry_stats,
        "attemptedUniqueUrls": attempted_urls,
        "resultBindings": len(results),
        "validatedVrms": statuses.get("valid_vrm", 0),
        "collectionsWithValidatedVrms": len(valid_collections),
        "validatedBytes": validated_bytes,
        "statusCounts": dict(sorted(statuses.items())),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = load_json(args.source)
    staging = load_json(args.staging)
    skipped = stageable_collection_ids(staging)
    candidates, stats = build_candidate_registry(source, skipped)
    selected = candidates[: max(0, int(args.max_candidates))] if args.max_candidates else candidates
    policy = CrawlPolicy(
        max_depth=0,
        request_budget=max(2_000, len(selected) * 20),
        max_tasks=max(20_000, len(selected) * 2),
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        max_document_bytes=2_000_000,
        max_vrm_json_bytes=4_000_000,
        max_vrm_bytes=args.max_vrm_bytes,
        max_links_per_document=0,
    )
    audited: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(validate_candidate, candidate, policy, args.max_attempts): candidate
            for candidate in selected
        }
        completed = 0
        for future in as_completed(futures):
            audited.append(future.result())
            completed += 1
            if completed % 10 == 0 or completed == len(selected):
                print(f"validated {completed}/{len(selected)} unique Moralis candidates", file=sys.stderr)

    audited.sort(key=lambda item: item["candidate"]["canonical_url"])
    observed_at = now_iso()
    results = expand_results(audited, observed_at)
    payload = {
        "schema": "moralis-candidate-binary-validation-v1",
        "generatedAt": observed_at,
        "sourceGeneratedAt": source.get("generatedAt"),
        "policy": (
            "Moralis is lead-only; promotion eligibility requires complete GLB 2.0 "
            "binary validation with VRM/VRMC_vrm, canonical URI and whole-file SHA-256"
        ),
        "summary": summarize(results, stats, len(selected)),
        "results": results,
        "validatedHits": [
            row
            for row in results
            if row.get("status") == "valid_vrm"
            and row.get("vrm_spec")
            and row.get("sha256")
            and row.get("canonical_url")
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-candidates", type=int, default=160)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--max-vrm-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    payload = run(args)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
