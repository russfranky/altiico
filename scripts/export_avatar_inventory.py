#!/usr/bin/env python3
"""Export the catalog's usable rigged-avatar inventory across supported formats.

This is intentionally layered on top of the existing VRM inventory instead of
replacing it. VRM remains the strongest self-describing avatar format, but a
collection can also satisfy the avatar-delivery requirement with an exhaustive
inventory of rigged GLB files or evidence-backed rigged FBX files.

Compatibility rules:
- Existing complete VRM inventories are imported as ``format=vrm`` assets.
- Legacy VRM terminal states such as ``not_shipped`` do NOT imply that no GLB or
  FBX avatar shipped. Only ``avatar_inventory`` may terminally resolve the
  broader multi-format inventory.
- ``avatar_inventory.assets`` is the preferred research shape for GLB/FBX.
- Explicitly catalog-bound OpenPage VRM/GLB discoveries are merged as partial
  candidates. They never make an inventory exhaustive by themselves.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research.json"
DEFAULT_VRM_INVENTORY = ROOT / "static" / "data" / "vrm-inventory.json"
DEFAULT_OPENPAGE_ASSETS = ROOT / "data" / "openpage_asset_discovery.json"
DEFAULT_OUTPUT = ROOT / "static" / "data" / "avatar-inventory.json"
SUPPORTED_FORMATS = {"vrm", "glb", "fbx"}
TERMINAL_RESEARCH_STATES = {"not_shipped", "unrecoverable"}
URL_PREFIXES = ("http://", "https://", "ipfs://", "ar://")


def has(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else fallback


def valid_url(raw: Any) -> bool:
    value = str(raw or "").strip()
    return bool(
        value
        and value.startswith(URL_PREFIXES)
        and not any(ch.isspace() for ch in value)
    )


def evidence(field: Any) -> list[dict[str, Any]]:
    if not isinstance(field, dict) or not isinstance(field.get("evidence"), list):
        return []
    return [row for row in field["evidence"] if isinstance(row, dict) and row]


def infer_format(url: str, explicit: Any = None, default: str | None = None) -> str:
    named = str(explicit or "").strip().lower().lstrip(".")
    if named in SUPPORTED_FORMATS:
        return named
    try:
        path = urllib.parse.urlsplit(str(url)).path.lower()
    except ValueError:
        path = str(url).lower()
    for fmt in SUPPORTED_FORMATS:
        if path.endswith(f".{fmt}"):
            return fmt
    return default if default in SUPPORTED_FORMATS else "unknown"


def storage_for_urls(urls: list[str]) -> list[str]:
    providers: set[str] = set()
    for raw in urls:
        url = raw.lower()
        if url.startswith("ipfs://") or "/ipfs/" in url:
            providers.add("ipfs")
        elif url.startswith("ar://") or "arweave.net/" in url:
            providers.add("arweave")
        elif url.startswith(("http://", "https://")):
            providers.add("https")
        elif url.startswith(("ethereum:", "data:")):
            providers.add("onchain")
    return sorted(providers)


def normalize_asset(
    raw: Any,
    *,
    default_format: str | None = None,
    inherited_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    inherited_evidence = inherited_evidence or []
    if isinstance(raw, str):
        url = raw.strip()
        if not valid_url(url):
            return None
        fmt = infer_format(url, default=default_format)
        return {
            "url": url,
            "format": fmt,
            "rigged": True if fmt == "vrm" else None,
            "rigging_evidence": [],
            "source_evidence": [],
        }
    if not isinstance(raw, dict):
        return None
    url = str(raw.get("url") or raw.get("href") or "").strip()
    if not valid_url(url):
        return None
    fmt = infer_format(url, raw.get("format"), default_format)
    rigging_evidence = raw.get("rigging_evidence")
    if not isinstance(rigging_evidence, list):
        rigging_evidence = raw.get("riggingEvidence")
    if not isinstance(rigging_evidence, list):
        rigging_evidence = []
    rigging_evidence = [row for row in rigging_evidence if isinstance(row, dict) and row]
    source_evidence = raw.get("source_evidence")
    if not isinstance(source_evidence, list):
        source_evidence = raw.get("sourceEvidence")
    if not isinstance(source_evidence, list):
        source_evidence = []
    source_evidence = [row for row in source_evidence if isinstance(row, dict) and row]
    if raw.get("rigged") is True and not rigging_evidence and fmt == "fbx":
        # Collection-level evidence is allowed to support an explicitly rigged
        # FBX declaration when the asset is part of the evidenced inventory.
        rigging_evidence = list(inherited_evidence)
    return {
        "url": url,
        "format": fmt,
        "rigged": True if fmt == "vrm" else raw.get("rigged"),
        "rigging_evidence": rigging_evidence,
        "source_evidence": source_evidence,
    }


def merge_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for asset in assets:
        url = str(asset.get("url") or "").strip()
        if not url:
            continue
        current = merged.get(url)
        if current is None:
            merged[url] = dict(asset)
            continue
        if current.get("format") == "unknown" and asset.get("format") != "unknown":
            current["format"] = asset.get("format")
        if asset.get("rigged") is True:
            current["rigged"] = True
        for field in ("rigging_evidence", "source_evidence"):
            evidence_rows = list(current.get(field) or [])
            for row in asset.get(field) or []:
                if row not in evidence_rows:
                    evidence_rows.append(row)
            current[field] = evidence_rows
    return [merged[url] for url in sorted(merged)]


def research_assets(research_row: dict[str, Any]) -> list[dict[str, Any]]:
    inv = research_row.get("avatar_inventory")
    if not isinstance(inv, dict):
        return []
    inherited = evidence(inv)
    raw_assets: list[Any] = []
    if isinstance(inv.get("assets"), list):
        raw_assets.extend(inv["assets"])
    if isinstance(inv.get("urls"), list):
        raw_assets.extend(inv["urls"])
    for key, fmt in (("vrm_urls", "vrm"), ("glb_urls", "glb"), ("fbx_urls", "fbx")):
        rows = inv.get(key)
        if isinstance(rows, list):
            raw_assets.extend({"url": row, "format": fmt} for row in rows)
    out = [
        asset
        for raw in raw_assets
        if (asset := normalize_asset(raw, inherited_evidence=inherited)) is not None
    ]
    return merge_assets(out)


def vrm_assets(vrm_row: dict[str, Any]) -> list[dict[str, Any]]:
    return merge_assets(
        [
            asset
            for url in vrm_row.get("urls") or []
            if (asset := normalize_asset(url, default_format="vrm")) is not None
        ]
    )


def openpage_asset_index(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Index only explicitly catalog-bound OpenPage candidate assets.

    Display-name similarity and OpenPage IDs are deliberately insufficient for
    catalog binding. The upstream discovery report must contain ``catalogId``.
    """
    indexed: dict[str, list[dict[str, Any]]] = {}
    rows = payload.get("records")
    if not isinstance(rows, list):
        return indexed

    for row in rows:
        if not isinstance(row, dict):
            continue
        collection_id = str(row.get("catalogId") or "").strip()
        if not collection_id:
            continue
        openpage_id = str(row.get("openpageId") or "").strip() or None
        candidates: list[dict[str, Any]] = []

        for key, fmt in (("vrmCandidates", "vrm"), ("glbUrls", "glb")):
            hits = row.get(key)
            if not isinstance(hits, list):
                continue
            for hit in hits:
                if isinstance(hit, str):
                    url = hit.strip()
                    source = None
                    via = "openpage_asset_discovery"
                elif isinstance(hit, dict):
                    url = str(hit.get("url") or "").strip()
                    source = hit.get("source")
                    via = hit.get("via") or "openpage_asset_discovery"
                else:
                    continue
                if not valid_url(url):
                    continue
                source_row = {
                    "kind": "openpage_asset_candidate",
                    "source": "OpenPage",
                    "openpage_id": openpage_id,
                    "record_index": row.get("recordIndex"),
                    "source_path": source,
                    "via": via,
                }
                source_row = {key: value for key, value in source_row.items() if value is not None}
                asset = normalize_asset(
                    {
                        "url": url,
                        "format": fmt,
                        "source_evidence": [source_row],
                    }
                )
                if asset is not None:
                    candidates.append(asset)

        if candidates:
            indexed.setdefault(collection_id, []).extend(candidates)

    return {
        collection_id: merge_assets(assets)
        for collection_id, assets in indexed.items()
    }


def access_for(research_row: dict[str, Any], vrm_row: dict[str, Any]) -> dict[str, Any]:
    override = (
        research_row.get("avatar_file_access")
        or research_row.get("source_3d_file_access")
        or research_row.get("file_access")
    )
    if isinstance(override, dict) and evidence(override):
        return {
            "mode": str(override.get("mode") or override.get("value") or "").strip().lower() or None,
            "requires_ownership": override.get("requires_ownership"),
            "access_url": override.get("access_url"),
            "evidence": evidence(override),
        }
    base = vrm_row.get("access")
    return dict(base) if isinstance(base, dict) else {
        "mode": None,
        "requires_ownership": None,
        "access_url": None,
        "evidence": [],
    }


def storage_for(
    research_row: dict[str, Any],
    vrm_row: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    override = research_row.get("avatar_storage") or research_row.get("storage")
    if isinstance(override, dict) and evidence(override):
        raw = override.get("value")
        if isinstance(raw, list):
            types = sorted({str(value) for value in raw if has(value)})
        elif has(raw):
            types = [str(raw)]
        else:
            types = storage_for_urls([asset["url"] for asset in assets])
        return {
            "types": types,
            "scope": str(override.get("scope") or "avatar_files"),
            "evidence": evidence(override),
        }
    derived = storage_for_urls([asset["url"] for asset in assets])
    if derived:
        return {"types": derived, "scope": "avatar_files", "evidence": []}
    base = vrm_row.get("storage")
    return dict(base) if isinstance(base, dict) else {"types": [], "scope": "avatar_files", "evidence": []}


def inventory_for(
    vrm_row: dict[str, Any],
    research_row: dict[str, Any],
    openpage_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_assets = vrm_assets(vrm_row)
    researched_assets = research_assets(research_row)
    discovered_assets = openpage_assets or []
    assets = merge_assets(base_assets + researched_assets + discovered_assets)
    urls = [asset["url"] for asset in assets]

    avatar_override = research_row.get("avatar_inventory")
    override_evidence = evidence(avatar_override)
    override_state = ""
    if isinstance(avatar_override, dict):
        override_state = str(
            avatar_override.get("state") or avatar_override.get("coverage") or ""
        ).strip().lower()

    state = "unknown"
    complete = False
    terminal = False
    coverage_source = None

    if override_state in TERMINAL_RESEARCH_STATES and override_evidence and not researched_assets:
        state = override_state
        complete = True
        terminal = True
        coverage_source = "avatar_catalog_research"
    elif override_state == "complete" and override_evidence and researched_assets:
        state = "complete"
        complete = True
        coverage_source = "avatar_catalog_research"
    elif str(vrm_row.get("state") or "").strip().lower() == "complete" and vrm_row.get("complete") and base_assets:
        # A complete VRM lane is already a complete usable avatar representation.
        state = "complete"
        complete = True
        coverage_source = "complete_vrm_inventory"
    elif assets:
        state = "partial"
        coverage_source = (
            "openpage_candidates"
            if discovered_assets and not (base_assets or researched_assets)
            else "partial_supported_avatar_assets"
        )

    format_counts: dict[str, int] = {}
    for asset in assets:
        fmt = str(asset.get("format") or "unknown")
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    return {
        "collection_id": str(vrm_row.get("collection_id") or ""),
        "name": vrm_row.get("name"),
        "state": state,
        "complete": complete,
        "terminal": terminal,
        "coverage_source": coverage_source,
        "expected_models": vrm_row.get("expected_models"),
        "enumerated_assets": len(assets),
        "enumerated_urls": len(urls),
        "formats": dict(sorted(format_counts.items())),
        "assets": assets,
        "urls": urls,
        "storage": storage_for(research_row, vrm_row, assets),
        "access": access_for(research_row, vrm_row),
        "inventory_evidence": override_evidence if override_evidence else (
            vrm_row.get("inventory_evidence") or []
            if state == "complete" and coverage_source == "complete_vrm_inventory"
            else []
        ),
        "legacy_vrm_state": vrm_row.get("state"),
    }


def run(
    research_path: Path,
    vrm_inventory_path: Path,
    output_path: Path,
    openpage_assets_path: Path = DEFAULT_OPENPAGE_ASSETS,
) -> dict[str, Any]:
    research_payload = load_json(research_path, {"collections": {}})
    research = research_payload.get("collections")
    if not isinstance(research, dict):
        research = {}
    vrm_payload = load_json(vrm_inventory_path, {"collections": []})
    vrm_rows = [row for row in vrm_payload.get("collections") or [] if isinstance(row, dict)]
    openpage_payload = load_json(openpage_assets_path, {"records": []})
    openpage_by_collection = openpage_asset_index(openpage_payload)
    inventories = [
        inventory_for(
            row,
            research.get(str(row.get("collection_id"))) or {},
            openpage_by_collection.get(str(row.get("collection_id"))) or [],
        )
        for row in vrm_rows
    ]
    openpage_candidate_assets = sum(
        any(
            evidence_row.get("kind") == "openpage_asset_candidate"
            for evidence_row in asset.get("source_evidence") or []
        )
        for row in inventories
        for asset in row["assets"]
    )
    openpage_candidate_collections = sum(
        any(
            any(
                evidence_row.get("kind") == "openpage_asset_candidate"
                for evidence_row in asset.get("source_evidence") or []
            )
            for asset in row["assets"]
        )
        for row in inventories
    )
    payload = {
        "schema": "avatar-catalog-inventory-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceVrmGeneratedAt": vrm_payload.get("generatedAt"),
        "sourceOpenPageGeneratedAt": openpage_payload.get("generatedAt"),
        "policy": (
            "A collection may satisfy the usable-avatar requirement with one exhaustive supported representation lane: "
            "structurally valid VRM, rigged GLB, or evidence-backed rigged FBX. Legacy VRM not_shipped states do not "
            "terminally resolve the broader avatar inventory. Explicitly catalog-bound OpenPage VRM/GLB discoveries "
            "are merged as candidates only and cannot make an inventory exhaustive without separate coverage evidence."
        ),
        "summary": {
            "collections": len(inventories),
            "complete": sum(bool(row["complete"]) for row in inventories),
            "partial": sum(row["state"] == "partial" for row in inventories),
            "unknown": sum(row["state"] == "unknown" for row in inventories),
            "notShipped": sum(row["state"] == "not_shipped" for row in inventories),
            "unrecoverable": sum(row["state"] == "unrecoverable" for row in inventories),
            "enumeratedAssets": sum(int(row["enumerated_assets"]) for row in inventories),
            "openpageCandidateCollections": openpage_candidate_collections,
            "openpageCandidateAssets": openpage_candidate_assets,
        },
        "collections": inventories,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--vrm-inventory", type=Path, default=DEFAULT_VRM_INVENTORY)
    parser.add_argument("--openpage-assets", type=Path, default=DEFAULT_OPENPAGE_ASSETS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = run(args.research, args.vrm_inventory, args.output, args.openpage_assets)
    print(json.dumps(payload["summary"], indent=2))
    if args.strict and (payload["summary"]["partial"] or payload["summary"]["unknown"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
