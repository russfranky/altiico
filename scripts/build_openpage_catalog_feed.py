#!/usr/bin/env python3
"""Build a catalog-bound OpenPage avatar-asset discovery feed.

OpenPage discovery is useful only when a source record can be tied to a catalog
collection without display-name guessing. This adapter binds records by one of
three explicit mechanisms:

1. a valid ``catalogId`` already present on the record;
2. an NFT contract address that uniquely matches catalog research; or
3. a curator-supplied OpenPage record/community ID mapping.

Curated source records may also contain explicit OpenPage metadata requests.
Those requests are resolved before binding. Only documented metadata paths,
curator-provided paths, or explicit HTTP(S) URLs are fetched. OpenPage API keys
are never sent to another origin.

After binding, records are passed through ``openpage_asset_discovery``. MML can
optionally be fetched to surface referenced VRM/model-GLB candidates. Standalone
animation GLBs remain a separate evidence lane and never enter avatar inventory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from scripts.openpage_asset_discovery import build_report, record_list

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"
DEFAULT_BINDINGS = ROOT / "data" / "openpage_catalog_bindings.json"
DEFAULT_COMMUNITIES = ROOT / "data" / "openpage_communities.json"
DEFAULT_SOURCES = ROOT / "data" / "openpage_asset_sources.json"
DEFAULT_OUTPUT = ROOT / "data" / "openpage_asset_discovery.json"
DEFAULT_API_BASE = os.environ.get("OPENPAGE_API_BASE", "https://api.openpage.fun/v1")
MAX_SOURCE_BYTES = 2 * 1024 * 1024

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

REQUEST_LIST_KEYS = ("requests", "metadataRequests", "openpageRequests")
REQUEST_ALIAS_KEYS = {
    "mmlId",
    "mmlIds",
    "collectionMetadataId",
    "collectionMetadataIds",
    "fetchUrl",
    "fetchUrls",
}
REQUEST_ENDPOINTS = {
    "mml": "/m/mml/{id}",
    "collection_metadata": "/m/c/{id}",
}
REQUEST_KIND_ALIASES = {
    "mml": "mml",
    "mml_metadata": "mml",
    "collection": "collection_metadata",
    "collection_metadata": "collection_metadata",
    "url": "url",
    "metadata_url": "url",
    "source_url": "url",
}
SourceRequester = Callable[[str, str, str], Any]


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
            collection_id = text(
                row.get("id") or row.get("collection_id") or row.get("catalogId")
            )
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


def canonical_request_kind(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_")
    return REQUEST_KIND_ALIASES.get(raw, raw)


def normalize_request(raw: Any, *, default_kind: str | None = None) -> dict[str, Any] | None:
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return None
        if value.startswith(("http://", "https://")):
            return {"kind": default_kind or "url", "url": value}
        if default_kind:
            return {"kind": default_kind, "id": value}
        return None
    if not isinstance(raw, dict):
        return None
    row = dict(raw)
    row["kind"] = canonical_request_kind(row.get("kind") or default_kind or "url")
    return row


def request_specs(record: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for key in REQUEST_LIST_KEYS:
        rows = record.get(key)
        if isinstance(rows, list):
            for raw in rows:
                normalized = normalize_request(raw)
                if normalized:
                    specs.append(normalized)

    for key, kind in (
        ("mmlId", "mml"),
        ("mmlIds", "mml"),
        ("collectionMetadataId", "collection_metadata"),
        ("collectionMetadataIds", "collection_metadata"),
        ("fetchUrl", "url"),
        ("fetchUrls", "url"),
    ):
        raw = record.get(key)
        rows = raw if isinstance(raw, list) else [raw]
        for value in rows:
            normalized = normalize_request(value, default_kind=kind)
            if normalized:
                specs.append(normalized)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in specs:
        marker = json.dumps(spec, sort_keys=True, ensure_ascii=False, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(spec)
    return deduped


def request_url(spec: dict[str, Any], api_base: str) -> str:
    explicit_url = text(spec.get("url"))
    if explicit_url:
        parsed = urllib.parse.urlsplit(explicit_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("explicit OpenPage source URL must be HTTP(S)")
        return explicit_url

    kind = canonical_request_kind(spec.get("kind"))
    source_id = text(spec.get("id"))
    path_template = text(spec.get("path")) or REQUEST_ENDPOINTS.get(kind, "")
    if not path_template:
        raise ValueError(
            f"request kind {kind!r} needs an explicit URL or path template"
        )
    if "{id}" in path_template and not source_id:
        raise ValueError(f"request kind {kind!r} requires an id")
    try:
        path = path_template.format(id=urllib.parse.quote(source_id, safe=""))
    except (KeyError, ValueError) as exc:
        raise ValueError(f"invalid OpenPage path template: {exc}") from exc
    if path.startswith(("http://", "https://")):
        return request_url({"url": path}, api_base)
    return urllib.parse.urljoin(api_base.rstrip("/") + "/", path.lstrip("/"))


def same_origin(url: str, api_base: str) -> bool:
    left = urllib.parse.urlsplit(url)
    right = urllib.parse.urlsplit(api_base)
    return (
        left.scheme.lower(),
        left.hostname,
        left.port,
    ) == (
        right.scheme.lower(),
        right.hostname,
        right.port,
    )


def request_payload(
    url: str,
    api_key: str,
    api_base: str,
    timeout: float = 20.0,
) -> Any:
    headers = {
        "Accept": "application/json, text/plain;q=0.9, text/html;q=0.8",
        "User-Agent": "vrm-catalog-openpage-source-refresh/1.0",
    }
    if text(api_key) and same_origin(url, api_base):
        headers["X-Api-Key"] = api_key

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = response.read(MAX_SOURCE_BYTES + 1)
        if len(body) > MAX_SOURCE_BYTES:
            raise ValueError(
                f"OpenPage source exceeds {MAX_SOURCE_BYTES} byte intake limit"
            )
        content_type = text(response.headers.get("Content-Type")).lower()

    decoded = body.decode("utf-8", errors="replace")
    stripped = decoded.lstrip()
    if "json" in content_type or stripped.startswith(("{", "[")):
        try:
            return json.loads(decoded)
        except json.JSONDecodeError:
            if "json" in content_type:
                raise
    return decoded


def source_base_record(record: dict[str, Any]) -> dict[str, Any]:
    base = deepcopy(record)
    for key in (*REQUEST_LIST_KEYS, *REQUEST_ALIAS_KEYS):
        base.pop(key, None)
    return base


def resolve_source_record(
    record: dict[str, Any],
    *,
    source_index: int,
    api_base: str,
    api_key: str,
    requester: SourceRequester = request_payload,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    specs = request_specs(record)
    if not specs:
        return [deepcopy(record)], []

    base = source_base_record(record)
    resolved: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for request_index, spec in enumerate(specs):
        kind = canonical_request_kind(spec.get("kind"))
        event: dict[str, Any] = {
            "sourceIndex": source_index,
            "requestIndex": request_index,
            "kind": kind,
            "id": spec.get("id"),
        }
        try:
            url = request_url(spec, api_base)
            event["url"] = url
            payload = requester(url, api_key, api_base)
            expanded = deepcopy(base)
            expanded["openpageSource"] = {
                "kind": kind,
                "id": spec.get("id"),
                "url": url,
                "fetchedAt": now_iso(),
            }
            if kind == "mml":
                expanded["mmlUrl"] = url
            elif kind == "collection_metadata":
                expanded["collectionMetadataUrl"] = url
            else:
                expanded["resolvedSourceUrl"] = url

            if isinstance(payload, (dict, list)):
                expanded["openpagePayload"] = payload
            else:
                expanded["openpagePayloadText"] = str(payload)
            resolved.append(expanded)
            event["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            event["status"] = "error"
            event["error"] = f"{type(exc).__name__}: {exc}"[:1000]
        events.append(event)

    if not resolved:
        fallback = deepcopy(base)
        fallback["openpageSourceErrors"] = [
            event for event in events if event.get("status") == "error"
        ]
        resolved.append(fallback)
    return resolved, events


def source_records(
    paths: list[Path],
    binding_payload: Any,
    *,
    api_base: str = DEFAULT_API_BASE,
    api_key: str = "",
    requester: SourceRequester = request_payload,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    configured: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        configured.extend(record_list(load_json(path, {})))
    if isinstance(binding_payload, dict):
        seeds = binding_payload.get("seedRecords")
        if isinstance(seeds, list):
            configured.extend(row for row in seeds if isinstance(row, dict))

    records: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    cache: dict[tuple[str, str], Any] = {}

    def cached_requester(url: str, key: str, base: str) -> Any:
        marker = (url, base)
        if marker not in cache:
            cache[marker] = requester(url, key, base)
        return cache[marker]

    for source_index, record in enumerate(configured):
        expanded, source_events = resolve_source_record(
            record,
            source_index=source_index,
            api_base=api_base,
            api_key=api_key,
            requester=cached_requester,
        )
        records.extend(expanded)
        events.extend(source_events)
    return records, events


def source_context(record: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in (
        "sourceRecordId",
        "sourceUrl",
        "resolvedSourceUrl",
        "openpageSource",
        "catalogBinding",
    ):
        value = record.get(key)
        if value not in (None, "", [], {}):
            context[key] = value
    return context


def run(
    *,
    research_path: Path,
    bindings_path: Path,
    input_paths: list[Path],
    output_path: Path,
    fetch_mml: bool = False,
    api_base: str = DEFAULT_API_BASE,
    api_key: str = "",
    source_requester: SourceRequester = request_payload,
) -> dict[str, Any]:
    research = research_rows(load_json(research_path, {"collections": {}}))
    known_catalog_ids = set(research)
    contracts = contract_index(research)
    bindings_payload = load_json(
        bindings_path, {"bindings": [], "seedRecords": []}
    )
    explicit_bindings = binding_index(bindings_payload, known_catalog_ids)
    records, source_events = source_records(
        input_paths,
        bindings_payload,
        api_base=api_base,
        api_key=api_key,
        requester=source_requester,
    )

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
    for inspected, bound in zip(report.get("records") or [], bound_records):
        context = source_context(bound)
        if context:
            inspected["sourceContext"] = context

    method_counts: dict[str, int] = {}
    for row in binding_rows:
        method = row["method"]
        method_counts[method] = method_counts.get(method, 0) + 1

    source_ok = sum(event.get("status") == "ok" for event in source_events)
    source_failed = sum(event.get("status") == "error" for event in source_events)

    report["schema"] = "openpage-catalog-feed-v2"
    report["generatedAt"] = now_iso()
    report["bindingPolicy"] = (
        "Catalog binding uses explicit catalogId, unique contract-address identity, or curator-supplied OpenPage ID only. "
        "Display names and fuzzy similarity never bind records."
    )
    report["sourceRefresh"] = {
        "apiBase": api_base.rstrip("/"),
        "requestsConfigured": len(source_events),
        "requestsSucceeded": source_ok,
        "requestsFailed": source_failed,
        "events": source_events,
    }
    report["bindingSummary"] = {
        "records": len(binding_rows),
        "bound": sum(row["method"] != "unbound" for row in binding_rows),
        "unbound": sum(row["method"] == "unbound" for row in binding_rows),
        "methods": dict(sorted(method_counts.items())),
    }
    report["bindings"] = binding_rows
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
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
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENPAGE_API_KEY", ""),
        help="Optional OpenPage API key. It is sent only to the configured API origin.",
    )
    parser.add_argument(
        "--strict-source-fetch",
        action="store_true",
        help="Return non-zero when any explicitly configured source request fails.",
    )
    args = parser.parse_args()
    inputs = args.input or default_inputs()
    report = run(
        research_path=args.research,
        bindings_path=args.bindings,
        input_paths=inputs,
        output_path=args.output,
        fetch_mml=args.fetch_mml,
        api_base=args.api_base,
        api_key=args.api_key,
    )
    print(
        json.dumps(
            {
                **report["bindingSummary"],
                **report["summary"],
                "sourceRefresh": report["sourceRefresh"],
            },
            indent=2,
        )
    )
    if args.strict_source_fetch and report["sourceRefresh"]["requestsFailed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
