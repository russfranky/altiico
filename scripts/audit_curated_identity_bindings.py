#!/usr/bin/env python3
"""Audit curated VRM metadata bindings for cross-collection identity contamination.

The catalog intentionally combines evidence from many sources. This report catches a
narrow but dangerous failure mode: a curated registry documents an exact metadata URL
for one contract, while the catalog attaches that exact metadata URL to a collection
whose known contract set does not include the registry contract.

The audit is deliberately strict and report-only:
- no name matching;
- no host/domain similarity matching;
- no contract mutation;
- no catalog or staging mutation;
- only exact normalized metadata URL equality can create a finding.

This makes findings suitable for manual identity reconciliation without turning a
project relationship or naming similarity into canonical identity evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = ROOT / "data" / "awesome_3d_avatar_collections.md"
DEFAULT_DATA_DIR = ROOT / "static" / "data"
DEFAULT_BUILD_INFO = DEFAULT_DATA_DIR / "build-info.json"
DEFAULT_OUTPUT = ROOT / "data" / "curated_identity_audit.json"
ADDRESS_RE = re.compile(r"^0x[a-f0-9]{40}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_url(value: Any) -> str:
    """Normalize only syntax that does not change URL identity semantics."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urllib.parse.urlsplit(raw)
    except ValueError:
        return raw
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return raw
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def contract_set(collection: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    primary = str(collection.get("contract") or "").strip().lower()
    if ADDRESS_RE.fullmatch(primary):
        out.add(primary)
    for row in collection.get("contracts") or []:
        if not isinstance(row, dict):
            continue
        address = str(row.get("address") or "").strip().lower()
        if ADDRESS_RE.fullmatch(address):
            out.add(address)
    return out


def load_collections(build_info_path: Path, data_dir: Path) -> list[dict[str, Any]]:
    build = load_json(build_info_path)
    relative = ((build.get("files") or {}).get("collections"))
    if not relative:
        raise ValueError("build-info.json does not name the collections payload")
    payload = load_json(data_dir / str(relative))
    return [row for row in payload.get("collections") or [] if isinstance(row, dict)]


def parse_registry(text: str) -> list[dict[str, str]]:
    """Reuse the documented-metadata parser without making this audit depend on DB state."""
    from scripts.validate_documented_metadata import parse_registry as _parse_registry

    return _parse_registry(text)


def audit_bindings(
    registry_rows: list[dict[str, str]], collections: list[dict[str, Any]]
) -> dict[str, Any]:
    metadata_index: dict[str, list[dict[str, Any]]] = {}
    exact_contract_index: dict[str, list[dict[str, Any]]] = {}
    for collection in collections:
        metadata_url = normalize_url(collection.get("sample_metadata_url"))
        if metadata_url:
            metadata_index.setdefault(metadata_url, []).append(collection)
        for contract in contract_set(collection):
            exact_contract_index.setdefault(contract, []).append(collection)

    findings: list[dict[str, Any]] = []
    registry_with_catalog_metadata_match = 0
    for row in registry_rows:
        registry_contract = str(row.get("contract") or "").strip().lower()
        metadata_url = normalize_url(row.get("metadataUrl"))
        if not ADDRESS_RE.fullmatch(registry_contract) or not metadata_url:
            continue
        metadata_matches = metadata_index.get(metadata_url, [])
        if metadata_matches:
            registry_with_catalog_metadata_match += 1
        exact_contract_matches = exact_contract_index.get(registry_contract, [])
        exact_ids = sorted(
            str(item.get("id")) for item in exact_contract_matches if item.get("id")
        )
        for collection in metadata_matches:
            catalog_contracts = contract_set(collection)
            if registry_contract in catalog_contracts:
                continue
            findings.append(
                {
                    "type": "exact_metadata_url_bound_to_different_contract",
                    "registryName": row.get("registryName"),
                    "registryContract": registry_contract,
                    "metadataUrl": row.get("metadataUrl"),
                    "catalogId": collection.get("id"),
                    "catalogName": collection.get("name"),
                    "catalogPrimaryContract": collection.get("contract"),
                    "catalogContracts": sorted(catalog_contracts),
                    "registryContractCatalogIds": exact_ids,
                    "catalogVrmParam": collection.get("vrm_param"),
                    "catalogVrmUrl": collection.get("vrm_url_https"),
                    "catalogVrmCheckStatus": collection.get("vrm_check_status"),
                }
            )

    findings.sort(
        key=lambda item: (
            str(item.get("registryName") or "").casefold(),
            str(item.get("catalogId") or ""),
        )
    )
    return {
        "schema": "curated-identity-binding-audit-v1",
        "generatedAt": now_iso(),
        "policy": (
            "findings require exact normalized metadata URL equality plus a contract "
            "mismatch; names and related project hosts are never identity evidence"
        ),
        "summary": {
            "registryRowsWithExplicitVrmField": len(registry_rows),
            "catalogCollections": len(collections),
            "registryRowsWithCatalogMetadataMatch": registry_with_catalog_metadata_match,
            "identityMismatchFindings": len(findings),
            "affectedCatalogCollections": len(
                {str(item.get("catalogId")) for item in findings if item.get("catalogId")}
            ),
        },
        "findings": findings,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    rows = parse_registry(args.registry.read_text(encoding="utf-8"))
    collections = load_collections(args.build_info, args.data_dir)
    payload = audit_bindings(rows, collections)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--build-info", type=Path, default=DEFAULT_BUILD_INFO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
