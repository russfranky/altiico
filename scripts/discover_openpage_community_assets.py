#!/usr/bin/env python3
"""Enumerate OpenPage community file/collection records without guessing routes.

The current OpenPage API publishes a machine-readable OpenAPI specification.
This adapter discovers relevant GET list operations from that specification,
then exhausts them for every community returned by
``discover_openpage_communities.py``. It does not bind records by display name.
A record receives ``catalogId`` only when the community ID has a curator binding;
otherwise the downstream catalog feed may still bind it through a unique NFT
contract found in the returned payload.

The output is generic on purpose: raw API items are preserved under
``openpagePayload`` so ``build_openpage_catalog_feed.py`` and
``openpage_asset_discovery.py`` can inspect nested MML, VRM, model-GLB, contract,
and metadata-ID fields without this script inventing a provider-specific schema.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMMUNITIES = ROOT / "data" / "openpage_communities.json"
DEFAULT_BINDINGS = ROOT / "data" / "openpage_catalog_bindings.json"
DEFAULT_OUTPUT = ROOT / "data" / "openpage_community_assets.json"
DEFAULT_API_BASE = os.environ.get("OPENPAGE_API_BASE", "https://api.openpage.fun/v1")
DEFAULT_OPENAPI_URLS = (
    "https://api.openpage.fun/v1/docs.json",
    "https://docs.openpage.fun/api-reference/openapi.json",
)
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
LIST_TERMS = (
    ("community_files", ("community files", "get files", "list files")),
    ("community_collections", ("community collections", "get collections", "list collections")),
    ("community_mintables", ("community mintables", "get mintables", "list mintables")),
)
PATH_SEGMENTS = {
    "file": "community_files",
    "files": "community_files",
    "collection": "community_collections",
    "collections": "community_collections",
    "mintable": "community_mintables",
    "mintables": "community_mintables",
}
PAGE_KEYS = ("page",)
PER_PAGE_KEYS = ("perpage", "per_page", "limit", "pagesize", "page_size")
PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
LIST_KEYS = ("results", "items", "files", "collections", "mintables", "records")
WRAPPER_KEYS = ("data", "payload", "response")
ASSET_HINT_KEYS = {
    "url",
    "href",
    "downloadurl",
    "download_url",
    "sourceurl",
    "source_url",
    "modelurl",
    "model_url",
    "mmlurl",
    "mml_url",
    "vrmurl",
    "vrm_url",
    "animationurl",
    "animation_url",
    "contract",
    "contractaddress",
    "contract_address",
    "mimetype",
    "mime_type",
    "filename",
    "file_name",
}
Requester = Callable[[str, str, str], Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def same_origin(url: str, api_base: str) -> bool:
    left = urllib.parse.urlsplit(url)
    right = urllib.parse.urlsplit(api_base)
    return (left.scheme.lower(), left.hostname, left.port) == (
        right.scheme.lower(), right.hostname, right.port
    )


def request_json(url: str, api_key: str, api_base: str, timeout: float = 20.0) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "vrm-catalog-openpage-community-assets/1.0",
    }
    if text(api_key) and same_origin(url, api_base):
        headers["X-Api-Key"] = api_key
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError(f"OpenPage response exceeds {MAX_RESPONSE_BYTES} bytes")
    return json.loads(body.decode("utf-8"))


def fetch_openapi(
    urls: Iterable[str],
    *,
    api_key: str,
    api_base: str,
    requester: Requester = request_json,
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    for url in urls:
        try:
            payload = requester(url, api_key, api_base)
            if not isinstance(payload, dict) or not isinstance(payload.get("paths"), dict):
                raise ValueError("OpenAPI response must contain an object-valued paths field")
            return payload, url, errors
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"[:1000]})
    raise RuntimeError("OpenPage OpenAPI discovery failed: " + json.dumps(errors))


def normalized_words(value: Any) -> str:
    raw = CAMEL_RE.sub(" ", text(value))
    raw = re.sub(r"[_/.-]+", " ", raw)
    return " ".join(raw.lower().split())


def operation_text(operation: dict[str, Any], path: str) -> str:
    tags = operation.get("tags") if isinstance(operation.get("tags"), list) else []
    values = [
        operation.get("operationId"),
        operation.get("summary"),
        operation.get("description"),
        *tags,
        path,
    ]
    return " ".join(normalized_words(value) for value in values)


def operation_parameters(operation: dict[str, Any], path_item: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in (path_item.get("parameters"), operation.get("parameters")):
        if isinstance(source, list):
            rows.extend(row for row in source if isinstance(row, dict))
    return rows


def dereference_parameter(parameter: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    ref = text(parameter.get("$ref"))
    if not ref.startswith("#/components/parameters/"):
        return parameter
    key = ref.rsplit("/", 1)[-1]
    components = spec.get("components") if isinstance(spec.get("components"), dict) else {}
    parameters = components.get("parameters") if isinstance(components.get("parameters"), dict) else {}
    resolved = parameters.get(key)
    return resolved if isinstance(resolved, dict) else parameter


def path_parameter_names(path: str) -> list[str]:
    return PLACEHOLDER_RE.findall(path)


def is_community_parameter(name: str, parameter: dict[str, Any]) -> bool:
    normalized = name.lower().replace("_", "")
    description = normalized_words(parameter.get("description"))
    return normalized in {"id", "communityid", "community"} or "community id" in description


def path_list_kind(path: str) -> str | None:
    segments = [
        segment.lower()
        for segment in urllib.parse.urlsplit(path).path.strip("/").split("/")
        if segment
    ]
    if not segments:
        return None
    for index, segment in enumerate(segments[:-1]):
        if segment == "community" and PLACEHOLDER_RE.fullmatch(segments[index + 1]):
            if index + 2 < len(segments) and index + 3 == len(segments):
                return PATH_SEGMENTS.get(segments[index + 2])
    return None


def discover_list_endpoints(spec: dict[str, Any]) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        operation = path_item.get("get")
        if not isinstance(operation, dict):
            continue
        combined = operation_text(operation, str(path))
        kind = path_list_kind(str(path))
        if kind is None:
            for candidate_kind, terms in LIST_TERMS:
                if any(term in combined for term in terms):
                    kind = candidate_kind
                    break
        if not kind:
            continue

        placeholders = path_parameter_names(str(path))
        if len(placeholders) != 1:
            continue
        parameters = [
            dereference_parameter(row, spec)
            for row in operation_parameters(operation, path_item)
        ]
        parameter_by_name = {
            text(row.get("name")): row
            for row in parameters
            if text(row.get("name"))
        }
        community_name = placeholders[0]
        community_parameter = parameter_by_name.get(community_name, {})
        if not is_community_parameter(community_name, community_parameter):
            continue

        query_names = {
            text(row.get("name"))
            for row in parameters
            if text(row.get("in")).lower() == "query" and text(row.get("name"))
        }
        discovered.append(
            {
                "kind": kind,
                "path": str(path),
                "communityParameter": community_name,
                "queryParameters": sorted(query_names),
                "operationId": operation.get("operationId"),
                "summary": operation.get("summary"),
                "tags": operation.get("tags") or [],
            }
        )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in discovered:
        deduped[(row["kind"], row["path"])] = row
    return [deduped[key] for key in sorted(deduped)]


def normalized_communities(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("communities")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and text(row.get("openpageId") or row.get("id"))]


def binding_map(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    indexed: dict[str, str] = {}
    rows = payload.get("bindings")
    if not isinstance(rows, list):
        return indexed
    for row in rows:
        if not isinstance(row, dict):
            continue
        community_id = text(
            row.get("openpageId")
            or row.get("openpage_id")
            or row.get("communityId")
            or row.get("community_id")
        )
        catalog_id = text(row.get("catalogId") or row.get("collection_id"))
        if not community_id or not catalog_id:
            continue
        previous = indexed.get(community_id)
        if previous and previous != catalog_id:
            raise ValueError(
                f"OpenPage community {community_id!r} maps to both {previous!r} and {catalog_id!r}"
            )
        indexed[community_id] = catalog_id
    return indexed


def query_key(names: set[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {name.lower().replace("-", "").replace("_", ""): name for name in names}
    for candidate in candidates:
        key = candidate.lower().replace("_", "")
        if key in normalized:
            return normalized[key]
    return None


def api_path_url(api_base: str, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    base = urllib.parse.urlsplit(api_base.rstrip("/"))
    base_path = base.path.rstrip("/")
    requested = "/" + path.lstrip("/")
    if base_path and (requested == base_path or requested.startswith(base_path + "/")):
        resolved_path = requested
    else:
        resolved_path = (base_path + requested) or "/"
    return urllib.parse.urlunsplit((base.scheme, base.netloc, resolved_path, "", ""))


def page_url(api_base: str, endpoint: dict[str, Any], community_id: str, page: int, per_page: int) -> str:
    path = endpoint["path"].replace(
        "{" + endpoint["communityParameter"] + "}",
        urllib.parse.quote(community_id, safe=""),
    )
    names = set(endpoint.get("queryParameters") or [])
    query: dict[str, Any] = {}
    page_name = query_key(names, PAGE_KEYS)
    per_page_name = query_key(names, PER_PAGE_KEYS)
    if page_name:
        query[page_name] = page
    if per_page_name:
        query[per_page_name] = per_page
    url = api_path_url(api_base, path)
    return url + ("?" + urllib.parse.urlencode(query) if query else "")


def reported_total(payload: dict[str, Any]) -> int | None:
    for key in ("total", "totalCount", "total_count", "count"):
        raw = payload.get(key)
        try:
            if raw is not None:
                return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def looks_like_asset_record(payload: dict[str, Any]) -> bool:
    normalized_keys = {
        str(key).lower().replace("-", "").replace(" ", "")
        for key in payload
    }
    normalized_hints = {
        key.lower().replace("-", "").replace(" ", "")
        for key in ASSET_HINT_KEYS
    }
    return bool(normalized_keys & normalized_hints)


def payload_items(payload: Any, depth: int = 0) -> tuple[list[dict[str, Any]], int | None]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)], None
    if not isinstance(payload, dict):
        return [], None

    outer_total = reported_total(payload)
    for key in LIST_KEYS:
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)], outer_total

    if depth < 3:
        for key in WRAPPER_KEYS:
            child = payload.get(key)
            if isinstance(child, (dict, list)):
                rows, child_total = payload_items(child, depth + 1)
                if rows:
                    return rows, outer_total if outer_total is not None else child_total

    if looks_like_asset_record(payload):
        return [payload], 1
    return [], outer_total


def enumerate_endpoint(
    endpoint: dict[str, Any],
    community: dict[str, Any],
    *,
    api_base: str,
    api_key: str,
    per_page: int,
    max_pages: int,
    requester: Requester,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    community_id = text(community.get("openpageId") or community.get("id"))
    page = 1
    pages = 0
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_reported: int | None = None
    truncated = False
    urls: list[str] = []

    while True:
        url = page_url(api_base, endpoint, community_id, page, per_page)
        urls.append(url)
        payload = requester(url, api_key, api_base)
        pages += 1
        rows, total = payload_items(payload)
        if total is not None:
            total_reported = total
        new_rows = 0
        for row in rows:
            marker = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            records.append(row)
            new_rows += 1

        if max_pages and pages >= max_pages:
            if total_reported is None or len(records) < total_reported:
                truncated = True
            break
        if total_reported is not None and len(records) >= total_reported:
            break
        if not rows or new_rows == 0 or len(rows) < per_page:
            break
        if not endpoint.get("queryParameters"):
            truncated = total_reported is not None and len(records) < total_reported
            break
        page += 1

    return records, {
        "communityId": community_id,
        "kind": endpoint["kind"],
        "path": endpoint["path"],
        "pages": pages,
        "items": len(records),
        "totalReported": total_reported,
        "truncated": truncated,
        "coverageComplete": not truncated and (total_reported is None or len(records) >= total_reported),
        "urls": urls,
    }


def run(
    *,
    communities_path: Path,
    bindings_path: Path,
    output_path: Path,
    api_base: str,
    api_key: str,
    openapi_urls: list[str],
    per_page: int = 100,
    max_pages: int = 0,
    requester: Requester = request_json,
) -> dict[str, Any]:
    communities = normalized_communities(load_json(communities_path, {"communities": []}))
    bindings = binding_map(load_json(bindings_path, {"bindings": []}))
    spec, spec_url, spec_errors = fetch_openapi(
        openapi_urls,
        api_key=api_key,
        api_base=api_base,
        requester=requester,
    )
    endpoints = discover_list_endpoints(spec)
    if not endpoints:
        raise RuntimeError("OpenPage OpenAPI contains no supported community asset list endpoint")

    records: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for community in communities:
        community_id = text(community.get("openpageId") or community.get("id"))
        catalog_id = bindings.get(community_id)
        for endpoint in endpoints:
            try:
                items, event = enumerate_endpoint(
                    endpoint,
                    community,
                    api_base=api_base,
                    api_key=api_key,
                    per_page=max(1, per_page),
                    max_pages=max(0, max_pages),
                    requester=requester,
                )
                events.append(event)
                for item_index, item in enumerate(items):
                    record = {
                        "openpageId": community_id,
                        "openpageCommunity": community,
                        "openpageEndpoint": {
                            "kind": endpoint["kind"],
                            "path": endpoint["path"],
                            "itemIndex": item_index,
                        },
                        "openpagePayload": item,
                    }
                    if catalog_id:
                        record["catalogId"] = catalog_id
                    records.append(record)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "communityId": community_id,
                        "kind": endpoint["kind"],
                        "path": endpoint["path"],
                        "error": f"{type(exc).__name__}: {exc}"[:1000],
                    }
                )

    report = {
        "schema": "openpage-community-assets-v2",
        "generatedAt": now_iso(),
        "source": {
            "apiBase": api_base.rstrip("/"),
            "openapiUrl": spec_url,
            "openapiFallbackErrors": spec_errors,
        },
        "policy": (
            "Routes are discovered from OpenPage's live OpenAPI specification. Records bind by curator-supplied "
            "OpenPage community ID or by unique contract identity downstream; display names never bind records."
        ),
        "summary": {
            "communities": len(communities),
            "endpoints": len(endpoints),
            "requestsSucceeded": len(events),
            "requestsFailed": len(errors),
            "items": len(records),
            "catalogBoundItems": sum(bool(row.get("catalogId")) for row in records),
            "coverageComplete": bool(communities) and bool(endpoints) and not errors and all(
                event.get("coverageComplete") is True for event in events
            ),
        },
        "endpoints": endpoints,
        "events": events,
        "errors": errors,
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--communities", type=Path, default=DEFAULT_COMMUNITIES)
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--api-key", default=os.environ.get("OPENPAGE_API_KEY", ""))
    parser.add_argument("--openapi-url", action="append", default=[])
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=0, help="0 = exhaust pagination")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if not text(args.api_key):
        raise SystemExit("OPENPAGE_API_KEY or --api-key is required")
    report = run(
        communities_path=args.communities,
        bindings_path=args.bindings,
        output_path=args.output,
        api_base=args.api_base,
        api_key=args.api_key,
        openapi_urls=args.openapi_url or list(DEFAULT_OPENAPI_URLS),
        per_page=args.per_page,
        max_pages=args.max_pages,
    )
    print(json.dumps(report["summary"], indent=2))
    if args.strict and (
        report["summary"]["requestsFailed"]
        or not report["summary"]["coverageComplete"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
