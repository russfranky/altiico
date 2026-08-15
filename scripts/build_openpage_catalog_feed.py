#!/usr/bin/env python3
"""Build a catalog-bound OpenPage avatar-asset discovery feed.

OpenPage discovery is useful only when a source record can be tied to a catalog
collection without display-name guessing. This adapter binds records by one of
three explicit mechanisms:

1. a valid ``catalogId`` already present on the record;
2. an NFT contract address that uniquely matches catalog research; or
3. a curator-supplied OpenPage record/community ID mapping.

After binding, records are passed through ``openpage_asset_discovery``. MML can
optionally be fetched to surface referenced VRM/model-GLB candidates. Standalone
animation GLBs remain a separate evidence lane and never enter avatar inventory.
"""
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.openpage_asset_discovery import build_report, record_list

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"
DEFAULT_BINDINGS = ROOT / "data" / "openpage_catalog_bindings.json"
DEFAULT_COMMUNITIES = ROOT / "data" / "openpage_communities.json"
DEFAULT_SOURCES = ROOT / "data" / "openpage_asset_sources.json"
DEFAULT_OUTPUT = ROOT / "data" / "openpage_asset_discovery.json"

CATALOG_ID_KEYS = ("catalogId", "catalog_id", "collection_id")
OPENPAGE_ID_KEYS = (
    "openpageId",
    "openpage_id",
    "avatarId",
    "avatar_id",
    "communityId",
    "community_id",
    "id",
)
CONTRACT_KEYS = {
    "contract",
    "contractaddress",
    "contract_address",
    "collectioncontract",
    "collection_contract",
    "nftcontract",
    "nft_contract",
}
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def text(value: Any) -> str:
    return str(value or "").strip()


def normalize_address(value: Any) -> str | None:
    raw = text(value)
    return raw.lower() if ADDRESS_RE.fullmatch(raw) else None


def explicit_value(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = text(record.get(key))
        if value:
            return value
    return None


def research_rows(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    collections = payload.get("collections")
    if isinstance(collections, dict):
        return {
            str(collection_id): row
            for collection_id, row in collections.items()
            if isinstance(row, dict)
        }
    if isinstance(collections, list):
        rows: dict[str, dict[str, Any]] = {}
        for row in collections:
            if not isinstance(row, dict):
                continue
            collection_id = text(row.get("id") or row.get("collection_id") or row.get("catalogId"))
            if collection_id:
                rows[collection_id] = row
        return rows
    return {}


def contract_index(research: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    indexed: dict[str, set[str]] = {}
    for collection_id, row in research.items():
        identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
        candidates = [
            row.get("contract"),
            row.get("contract_address"),
            identity.get("contract"),
            identity.get("contract_address"),
        ]
        for candidate in candidates:
            address = normalize_address(candidate)
            if address:
                indexed.setdefault(address, set()).add(collection_id)
    return indexed


def walk_contracts(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).replace("-", "").replace(" ", "").lower()
            if normalized_key in CONTRACT_KEYS or str(key).lower() in CONTRACT_KEYS:
                address = normalize_address(child)
                if address:
                    yield address
            yield from walk_contracts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_contracts(child)


def binding_index(payload: Any, known_catalog_ids: set[str]) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("bindings")
    if not isinstance(rows, list):
        return {}
    indexed: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        catalog_id = text(row.get("catalogId") or row.get("collection_id"))
        openpage_id = text(
            row.get("openpageId")
            or row.get("openpage_id")
            or row.get("communityId")
            or row.get("community_id")
        )
        if catalog_id not in known_catalog_ids or not openpage_id:
            continue
        previous = indexed.get(openpage_id)
        if previous and previous != catalog_id:
            raise ValueError(
                f"OpenPage ID {openpage_id!r} maps to both {previous!r} and {catalog_id!r}"
            )
        indexed[openpage_id] = catalog_id
    return indexed


def bind_record(
    record: dict[str, Any],
    *,
    known_catalog_ids: set[str],
    contracts: dict[str, set[str]],
    explicit_bindings: dict[str, str],
) -> tuple[dict[str, Any], str, list[str]]:
    """Return ``(record, binding_method, diagnostics)``.

    ``binding_method`` is one of ``catalog_id``, ``contract``, ``openpage_id`` or
    ``unbound``. Ambiguous contract matches stay unbound.
    """
    row = deepcopy(record)
    diagnostics: list[str] = []

    supplied_catalog_id = explicit_value(row, CATALOG_ID_KEYS)
    if supplied_catalog_id:
        if supplied_catalog_id in known_catalog_ids:
            row["catalogId"] = supplied_catalog_id
            for key in CATALOG_ID_KEYS:
                if key != "catalogId":
                    row.pop(key, None)
            return row, "catalog_id", diagnostics
        diagnostics.append(f"unknown_catalog_id:{supplied_catalog_id}")
        for key in CATALOG_ID_KEYS:
            row.pop(key, None)

    matched_ids: set[str] = set()
    matched_contracts: list[str] = []
    for address in sorted(set(walk_contracts(row))):
        catalog_ids = contracts.get(address) or set()
        if catalog_ids:
            matched_contracts.append(address)
            matched_ids.update(catalog_ids)

    if len(matched_ids) == 1:
        catalog_id = next(iter(matched_ids))
        row["catalogId"] = catalog_id
        row["catalogBinding"] = {
            "method": "contract",
            "contracts": matched_contracts,
        }
        return row, "contract", diagnostics
    if len(matched_ids) > 1:
        diagnostics.append("ambiguous_contract_binding:" + ",".join(sorted(matched_ids)))
        return row, "unbound", diagnostics

    for key in OPENPAGE_ID_KEYS:
        openpage_id = text(row.get(key))
        if not openpage_id:
            continue
        catalog_id = explicit_bindings.get(openpage_id)
        if catalog_id:
            row["catalogId"] = catalog_id
            row["catalogBinding"] = {
                "method": "openpage_id",
                "openpageId": openpage_id,
            }
            return row, "openpage_id", diagnostics

    diagnostics.append("no_explicit_binding")
    return row, "unbound", diagnostics


def source_records(paths: list[Path], binding_payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        records.extend(record_list(load_json(path, {})))
    if isinstance(binding_payload, dict):
        seeds = binding_payload.get("seedRecords")
        if isinstance(seeds, list):
            records.extend(row for row in seeds if isinstance(row, dict))
    return records


def run(
    *,
    research_path: Path,
    bindings_path: Path,
    input_paths: list[Path],
    output_path: Path,
    fetch_mml: bool = False,
) -> dict[str, Any]:
    research = research_rows(load_json(research_path, {"collections": {}}))
    known_catalog_ids = set(research)
    contracts = contract_index(research)
    bindings_payload = load_json(bindings_path, {"bindings": [], "seedRecords": []})
    explicit_bindings = binding_index(bindings_payload, known_catalog_ids)
    records = source_records(input_paths, bindings_payload)

    bound_records: list[dict[str, Any]] = []
    binding_rows: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        bound, method, diagnostics = bind_record(
            record,
            known_catalog_ids=known_catalog_ids,
            contracts=contracts,
            explicit_bindings=explicit_bindings,
        )
        bound_records.append(bound)
        binding_rows.append(
            {
                "recordIndex": index,
                "catalogId": bound.get("catalogId"),
                "method": method,
                "diagnostics": diagnostics,
            }
        )

    report = build_report(bound_records, fetch_mml=fetch_mml)
    method_counts: dict[str, int] = {}
    for row in binding_rows:
        method = row["method"]
        method_counts[method] = method_counts.get(method, 0) + 1

    report["schema"] = "openpage-catalog-feed-v1"
    report["generatedAt"] = now_iso()
    report["bindingPolicy"] = (
        "Catalog binding uses explicit catalogId, unique contract-address identity, or curator-supplied OpenPage ID only. "
        "Display names and fuzzy similarity never bind records."
    )
    report["bindingSummary"] = {
        "records": len(binding_rows),
        "bound": sum(row["method"] != "unbound" for row in binding_rows),
        "unbound": sum(row["method"] == "unbound" for row in binding_rows),
        "methods": dict(sorted(method_counts.items())),
    }
    report["bindings"] = binding_rows
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def default_inputs() -> list[Path]:
    return [path for path in (DEFAULT_COMMUNITIES, DEFAULT_SOURCES) if path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--input", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fetch-mml", action="store_true")
    args = parser.parse_args()
    inputs = args.input or default_inputs()
    report = run(
        research_path=args.research,
        bindings_path=args.bindings,
        input_paths=inputs,
        output_path=args.output,
        fetch_mml=args.fetch_mml,
    )
    print(json.dumps({**report["bindingSummary"], **report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
