#!/usr/bin/env python3
"""Load catalog research from a base file plus per-collection evidence shards.

`data/catalog_research.json` remains a valid source for compatibility. Additional
files under `data/catalog_research.d/*.json` are merged by collection id so the
catalog can scale to dozens of independently researched projects without one
monolithic conflict-prone JSON document.

A shard may be either:

    {"id": "collection-id", ...fields...}

or the same aggregate shape as the base file:

    {"schema": "vrm-catalog-research-v1", "collections": {...}}

Duplicate field definitions are allowed only when their JSON values are exactly
identical; conflicting evidence fails closed instead of silently choosing one.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_SCHEMA = "vrm-catalog-research-v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return payload


def _collections_from_payload(path: Path, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if isinstance(payload.get("collections"), dict):
        out: dict[str, dict[str, Any]] = {}
        for collection_id, row in payload["collections"].items():
            if not isinstance(row, dict):
                raise ValueError(f"{path}: collection {collection_id!r} must be an object")
            out[str(collection_id)] = row
        return out

    collection_id = str(payload.get("id") or "").strip()
    if not collection_id:
        raise ValueError(f"{path}: shard needs either `collections` or a top-level `id`")
    row = {key: value for key, value in payload.items() if key not in {"id", "schema", "policy"}}
    return {collection_id: row}


def _merge_collection(
    collection_id: str,
    target: dict[str, Any],
    incoming: dict[str, Any],
    *,
    source: Path,
) -> None:
    for field, value in incoming.items():
        if field not in target:
            target[field] = deepcopy(value)
            continue
        if target[field] != value:
            raise ValueError(
                f"conflicting catalog research for {collection_id}.{field} from {source}"
            )


def load_catalog_research(
    base_path: Path,
    shard_dir: Path | None = None,
) -> dict[str, Any]:
    if shard_dir is None:
        shard_dir = base_path.parent / "catalog_research.d"

    aggregate: dict[str, Any] = {
        "schema": DEFAULT_SCHEMA,
        "policy": "Merged base and per-collection evidence shards; conflicting definitions fail closed.",
        "collections": {},
        "sources": [],
    }

    source_paths: list[Path] = []
    if base_path.exists():
        source_paths.append(base_path)
    if shard_dir.exists():
        source_paths.extend(sorted(path for path in shard_dir.glob("*.json") if path.is_file()))

    for path in source_paths:
        payload = _load_json(path)
        if path == base_path:
            if payload.get("schema"):
                aggregate["schema"] = payload["schema"]
            if payload.get("policy"):
                aggregate["policy"] = payload["policy"]
        for collection_id, row in _collections_from_payload(path, payload).items():
            target = aggregate["collections"].setdefault(collection_id, {})
            _merge_collection(collection_id, target, row, source=path)
        aggregate["sources"].append(str(path))

    return aggregate
