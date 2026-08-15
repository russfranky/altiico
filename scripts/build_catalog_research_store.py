#!/usr/bin/env python3
"""Compile base + per-collection research shards into one deterministic JSON file.

Curator-authored base/shard evidence remains authoritative and conflicting shard
fields still fail closed in ``catalog_research_store``. Generated provider
overlays are applied afterward with fill-only recursive semantics: they may add
missing values but can never replace curator evidence. This lets a refreshed
OpenPage overlay persist useful descriptions/socials/media without making stale
provider data authoritative.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.catalog_research_store import load_catalog_research

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = ROOT / "data" / "catalog_research.json"
DEFAULT_SHARDS = ROOT / "data" / "catalog_research.d"
DEFAULT_OPENPAGE_OVERLAY = ROOT / "data" / "openpage_catalog_enrichment.json"
DEFAULT_OUTPUT = ROOT / "data" / "catalog_research_merged.json"


def load_overlay(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: overlay must be an object")
    collections = payload.get("collections")
    if not isinstance(collections, dict):
        raise ValueError(f"{path}: overlay collections must be an object")
    return payload


def fill_missing(
    target: dict[str, Any],
    incoming: dict[str, Any],
    *,
    prefix: str,
    filled: list[str],
    preserved: list[str],
) -> None:
    for key, value in incoming.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in target or target[key] in (None, "", [], {}):
            target[key] = deepcopy(value)
            filled.append(path)
            continue
        current = target[key]
        if isinstance(current, dict) and isinstance(value, dict):
            fill_missing(
                current,
                value,
                prefix=path,
                filled=filled,
                preserved=preserved,
            )
            continue
        if current != value:
            preserved.append(path)


def apply_overlay(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    overlay = load_overlay(path)
    filled: list[str] = []
    preserved: list[str] = []
    unknown_collections: list[str] = []
    for collection_id, incoming in sorted(overlay["collections"].items()):
        if not isinstance(incoming, dict):
            raise ValueError(f"{path}: collection {collection_id!r} must be an object")
        target = payload["collections"].get(str(collection_id))
        if not isinstance(target, dict):
            unknown_collections.append(str(collection_id))
            continue
        fill_missing(
            target,
            incoming,
            prefix=str(collection_id),
            filled=filled,
            preserved=preserved,
        )
    return {
        "path": str(path),
        "fieldsFilled": sorted(filled),
        "curatorFieldsPreserved": sorted(preserved),
        "unknownCollections": sorted(unknown_collections),
    }


def run(
    base: Path,
    shards: Path,
    output: Path,
    overlays: list[Path] | None = None,
) -> dict[str, Any]:
    payload = load_catalog_research(base, shards)
    if overlays is None:
        overlays = [DEFAULT_OPENPAGE_OVERLAY] if DEFAULT_OPENPAGE_OVERLAY.exists() else []
    overlay_results: list[dict[str, Any]] = []
    for path in overlays:
        if not path.exists():
            continue
        overlay_results.append(apply_overlay(payload, path))
        if str(path) not in payload["sources"]:
            payload["sources"].append(str(path))
    payload["collections"] = {
        key: payload["collections"][key] for key in sorted(payload["collections"])
    }
    payload["overlays"] = overlay_results
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--shards", type=Path, default=DEFAULT_SHARDS)
    parser.add_argument("--overlay", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    overlays = args.overlay or (
        [DEFAULT_OPENPAGE_OVERLAY] if DEFAULT_OPENPAGE_OVERLAY.exists() else []
    )
    payload = run(args.base, args.shards, args.output, overlays)
    print(
        json.dumps(
            {
                "collections": len(payload["collections"]),
                "sources": len(payload["sources"]),
                "overlays": len(payload["overlays"]),
                "overlayFieldsFilled": sum(
                    len(row["fieldsFilled"]) for row in payload["overlays"]
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
