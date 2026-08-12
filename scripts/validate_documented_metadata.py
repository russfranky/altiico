#!/usr/bin/env python3
"""Validate VRM pointers from curated, explicitly documented metadata examples.

This pass is deliberately report-only. It parses the committed
``awesome_3d_avatar_collections.md`` registry, selects rows whose Metadata Param
explicitly names a VRM field, binds each row to an existing catalog collection
by exact Ethereum contract, skips contracts that are already stageable, fetches
the documented example metadata, and binary-validates any VRM pointers found.

No collection, avatar, staging, or database row is modified by this script.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.crawler.fetch import NetworkLoader  # noqa: E402
from scripts.crawler.models import CrawlPolicy, PermanentCrawlError, RetryableCrawlError  # noqa: E402
from scripts.crawler.uri import canonicalize_uri  # noqa: E402
from scripts.discover_metadata_fields import scan_metadata  # noqa: E402

DEFAULT_REGISTRY = ROOT / "data" / "awesome_3d_avatar_collections.md"
DEFAULT_DB = ROOT / "data" / "vrm_index.db"
DEFAULT_STAGING = ROOT / "static" / "data" / "hubzz-prealpha-staging.json"
DEFAULT_OUTPUT = ROOT / "data" / "documented_metadata_validation.json"

LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)", re.IGNORECASE)
CONTRACT_RE = re.compile(r"/address/(0x[a-fA-F0-9]{40})(?:[/?#]|$)")
NAME_RE = re.compile(r"^\[([^\]]+)\]")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cell_name(cell: str) -> str:
    match = NAME_RE.search(cell.strip())
    return match.group(1).strip() if match else cell.strip()


def _first_link(cell: str) -> str | None:
    match = LINK_RE.search(cell)
    return match.group(1).strip() if match else None


def parse_registry(text: str) -> list[dict[str, str]]:
    """Return only rows that explicitly document a VRM metadata field."""
    rows: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0].casefold() == "creator":
            continue
        creator, contract_cell, metadata_cell, metadata_param = cells[:4]
        if "vrm:" not in metadata_param.casefold():
            continue
        contract_link = _first_link(contract_cell) or ""
        contract_match = CONTRACT_RE.search(contract_link)
        metadata_url = _first_link(metadata_cell)
        if not contract_match or not metadata_url:
            continue
        rows.append(
            {
                "registryName": _cell_name(creator),
                "contract": contract_match.group(1).lower(),
                "metadataUrl": metadata_url,
                "metadataParam": metadata_param,
            }
        )
    return rows


def catalog_by_contract(db_path: Path) -> dict[str, dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, name, chain, contract FROM collections "
            "WHERE lower(chain)='ethereum' AND contract IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        contract = str(row["contract"] or "").strip().lower()
        if re.fullmatch(r"0x[a-f0-9]{40}", contract):
            out[contract] = dict(row)
    return out


def stageable_contracts(staging: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in staging.get("sets") or []:
        if not isinstance(item, dict):
            continue
        set_row = item.get("set") or {}
        if not isinstance(set_row, dict):
            continue
        if str(set_row.get("chain") or "").casefold() != "ethereum":
            continue
        contract = str(set_row.get("contract") or "").strip().lower()
        if re.fullmatch(r"0x[a-f0-9]{40}", contract):
            out.add(contract)
    return out


def select_targets(
    registry_rows: list[dict[str, str]],
    catalog: dict[str, dict[str, Any]],
    already_stageable: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    targets: list[dict[str, Any]] = []
    missing_identity = 0
    skipped_stageable = 0
    seen: set[tuple[str, str]] = set()
    for row in registry_rows:
        contract = row["contract"]
        if contract in already_stageable:
            skipped_stageable += 1
            continue
        collection = catalog.get(contract)
        if not collection:
            missing_identity += 1
            continue
        identity = (contract, row["metadataUrl"])
        if identity in seen:
            continue
        seen.add(identity)
        targets.append({**row, "catalogId": collection["id"], "catalogName": collection["name"]})
    targets.sort(key=lambda row: (str(row["catalogName"]).casefold(), row["metadataUrl"]))
    return targets, {
        "registryRowsWithExplicitVrmField": len(registry_rows),
        "skippedAlreadyStageable": skipped_stageable,
        "skippedMissingExactCatalogIdentity": missing_identity,
        "selectedTargets": len(targets),
    }


def fetch_metadata(url: str, timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "vrm-catalog/1.0 documented-metadata-validation",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def validate_pointer(url: str, policy: CrawlPolicy, max_attempts: int) -> dict[str, Any]:
    try:
        canonical = canonicalize_uri(url)
    except (PermanentCrawlError, RetryableCrawlError) as exc:
        return {"url": url, "status": "invalid_uri", "error": str(exc)}

    loader = NetworkLoader(None, policy)
    errors: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        try:
            validation = asdict(loader.validate_vrm(canonical))
            return {
                "url": url,
                "canonicalUrl": canonical,
                "status": validation.get("status"),
                "vrmSpec": validation.get("vrm_spec"),
                "contentSha256": validation.get("content_sha256"),
                "jsonChunkSha256": validation.get("json_chunk_sha256"),
                "byteLength": validation.get("observed_length"),
                "transportUrl": validation.get("transport_url"),
                "error": validation.get("error"),
                "attempts": attempt,
                "validationErrors": errors,
            }
        except RetryableCrawlError as exc:
            errors.append({"attempt": attempt, "retryable": True, "error": str(exc)})
            if attempt < max_attempts:
                delay = exc.retry_after if exc.retry_after is not None else 2 ** (attempt - 1)
                time.sleep(min(5.0, max(0.0, float(delay))))
        except PermanentCrawlError as exc:
            errors.append({"attempt": attempt, "retryable": False, "error": str(exc)})
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "attempt": attempt,
                    "retryable": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            break
    return {
        "url": url,
        "canonicalUrl": canonical,
        "status": "transport_error",
        "error": errors[-1]["error"] if errors else "validation_failed",
        "validationErrors": errors,
    }


def inspect_target(target: dict[str, Any], policy: CrawlPolicy, timeout: float, max_attempts: int) -> dict[str, Any]:
    result = {**target, "metadataFetch": "ok", "metadataError": None, "candidates": []}
    try:
        metadata = fetch_metadata(target["metadataUrl"], timeout)
    except Exception as exc:  # noqa: BLE001
        result["metadataFetch"] = "error"
        result["metadataError"] = f"{type(exc).__name__}: {exc}"[:500]
        return result

    candidates = scan_metadata(metadata)
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if url and url not in deduped:
            deduped[url] = candidate
    for url, candidate in deduped.items():
        result["candidates"].append(
            {
                "path": candidate.get("path"),
                "field": candidate.get("field"),
                "reason": candidate.get("reason"),
                **validate_pointer(url, policy, max_attempts),
            }
        )
    return result


def summarize(results: list[dict[str, Any]], selection: dict[str, int]) -> dict[str, Any]:
    metadata_errors = sum(row.get("metadataFetch") != "ok" for row in results)
    candidate_count = sum(len(row.get("candidates") or []) for row in results)
    valid = [
        candidate
        for row in results
        for candidate in row.get("candidates") or []
        if candidate.get("status") == "valid_vrm"
        and candidate.get("vrmSpec")
        and candidate.get("contentSha256")
    ]
    valid_collections = {
        row["catalogId"]
        for row in results
        if any(
            candidate.get("status") == "valid_vrm"
            and candidate.get("vrmSpec")
            and candidate.get("contentSha256")
            for candidate in row.get("candidates") or []
        )
    }
    return {
        **selection,
        "metadataFetchErrors": metadata_errors,
        "pointerCandidates": candidate_count,
        "validatedVrms": len(valid),
        "collectionsWithValidatedVrms": len(valid_collections),
        "validatedBytes": sum(int(candidate.get("byteLength") or 0) for candidate in valid),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    registry_rows = parse_registry(args.registry.read_text(encoding="utf-8"))
    catalog = catalog_by_contract(args.db)
    staging = load_json(args.staging)
    targets, selection = select_targets(registry_rows, catalog, stageable_contracts(staging))
    if args.max_targets:
        targets = targets[: max(0, int(args.max_targets))]
        selection["selectedTargets"] = len(targets)

    policy = CrawlPolicy(
        max_depth=0,
        request_budget=max(500, len(targets) * 20),
        max_tasks=max(5_000, len(targets) * 5),
        max_attempts=args.max_attempts,
        timeout=args.timeout,
        max_document_bytes=2_000_000,
        max_vrm_json_bytes=4_000_000,
        max_vrm_bytes=args.max_vrm_bytes,
        max_links_per_document=0,
    )
    results = [inspect_target(target, policy, args.timeout, args.max_attempts) for target in targets]
    payload = {
        "schema": "documented-metadata-binary-validation-v1",
        "generatedAt": now_iso(),
        "source": str(args.registry.relative_to(ROOT) if args.registry.is_relative_to(ROOT) else args.registry),
        "policy": (
            "curated registry metadata is lead evidence only; a hit requires exact contract identity "
            "plus complete GLB 2.0 VRM/VRMC_vrm validation with whole-file SHA-256"
        ),
        "summary": summarize(results, selection),
        "results": results,
        "validatedHits": [
            {
                "catalogId": row["catalogId"],
                "catalogName": row["catalogName"],
                "contract": row["contract"],
                "metadataUrl": row["metadataUrl"],
                "candidate": candidate,
            }
            for row in results
            for candidate in row.get("candidates") or []
            if candidate.get("status") == "valid_vrm"
            and candidate.get("vrmSpec")
            and candidate.get("contentSha256")
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-targets", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--max-vrm-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    payload = run(args)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
