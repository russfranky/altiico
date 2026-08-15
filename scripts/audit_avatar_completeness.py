#!/usr/bin/env python3
"""Audit collection completeness using the multi-format avatar inventory.

The existing catalog audit remains useful for all non-model research dimensions.
This wrapper replaces the VRM-only inventory/storage/access decision with the
broader avatar inventory, where a complete VRM, rigged GLB, or evidence-backed
rigged FBX lane can satisfy the model requirement.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_catalog_completeness import (
    DEFAULT_DB,
    DEFAULT_RESEARCH,
    REQUIRED_FIELDS as LEGACY_REQUIRED_FIELDS,
    run as run_legacy,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = ROOT / "static" / "data" / "avatar-inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "catalog_completeness_report.json"
TERMINAL_STATES = {"not_shipped", "unrecoverable"}
ACCESS_MODES = {"public", "holder_gated", "account_gated", "unavailable"}
REQUIRED_FIELDS = tuple(
    "avatar_inventory" if name == "vrm_inventory" else name
    for name in LEGACY_REQUIRED_FIELDS
)


def has(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inventory_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("collection_id")): row
        for row in payload.get("collections") or []
        if isinstance(row, dict) and row.get("collection_id")
    }


def avatar_inventory_field(inventory: dict[str, Any] | None) -> dict[str, Any]:
    if not inventory:
        return {"ok": False, "state": "missing"}
    state = str(inventory.get("state") or "").strip().lower()
    assets = inventory.get("assets") or []
    evidence = inventory.get("inventory_evidence") or []
    complete = bool(inventory.get("complete"))
    if state == "complete" and complete and assets:
        return {
            "ok": True,
            "state": "complete",
            "value": {
                "known_assets": len(assets),
                "expected": inventory.get("expected_models"),
                "formats": inventory.get("formats") or {},
                "coverage": "complete",
            },
            "source": "avatar_inventory",
        }
    if state in TERMINAL_STATES and complete and evidence:
        return {
            "ok": True,
            "state": state,
            "value": {
                "known_assets": 0,
                "expected": inventory.get("expected_models"),
                "formats": {},
                "coverage": state,
            },
            "source": "avatar_inventory",
            "evidence": evidence,
        }
    return {
        "ok": False,
        "state": state or "unknown",
        "value": {
            "known_assets": len(assets),
            "expected": inventory.get("expected_models"),
            "formats": inventory.get("formats") or {},
            "coverage": state or "unknown",
        },
        "source": "avatar_inventory",
    }


def storage_field(inventory: dict[str, Any] | None) -> dict[str, Any]:
    if not inventory:
        return {"ok": False, "state": "unknown"}
    storage = inventory.get("storage") or {}
    types = storage.get("types") or []
    if types:
        value: Any = types[0] if len(types) == 1 else types
        return {
            "ok": True,
            "state": "present",
            "value": value,
            "source": "avatar_inventory.storage",
            "evidence": storage.get("evidence") or [],
            "detail": {"scope": storage.get("scope")},
        }
    return {"ok": False, "state": "unknown", "source": "avatar_inventory.storage"}


def access_field(inventory: dict[str, Any] | None) -> dict[str, Any]:
    if not inventory:
        return {"ok": False, "state": "unknown"}
    state = str(inventory.get("state") or "").strip().lower()
    access = inventory.get("access") or {}
    mode = str(access.get("mode") or "").strip().lower()
    requires_ownership = access.get("requires_ownership")
    evidence = access.get("evidence") or []
    if state in TERMINAL_STATES and mode == "unavailable" and evidence:
        return {
            "ok": True,
            "state": "unavailable",
            "value": "unavailable",
            "source": "avatar_inventory.access",
            "evidence": evidence,
        }
    ok = mode in ACCESS_MODES - {"unavailable"} and isinstance(requires_ownership, bool)
    if mode == "holder_gated" and requires_ownership is not True:
        ok = False
    if mode == "public" and requires_ownership is not False:
        ok = False
    return {
        "ok": ok,
        "state": "present" if ok else "unknown",
        "value": mode or None,
        "source": "avatar_inventory.access",
        "evidence": evidence,
        "detail": {
            "requires_ownership": requires_ownership,
            "access_url": access.get("access_url"),
        },
    }


def run(
    db_path: Path,
    research_path: Path,
    inventory_path: Path,
    output_path: Path | None = None,
    tiers: set[str] | None = None,
) -> dict[str, Any]:
    legacy = run_legacy(db_path, research_path, None, tiers)
    inventories = inventory_index(load(inventory_path))
    results: list[dict[str, Any]] = []
    for collection in legacy.get("collections") or []:
        if not isinstance(collection, dict):
            continue
        row = dict(collection)
        fields = dict(row.get("fields") or {})
        inventory = inventories.get(str(row.get("id")))
        fields["avatar_inventory"] = avatar_inventory_field(inventory)
        fields["storage"] = storage_field(inventory)
        fields["file_access"] = access_field(inventory)
        # Preserve the VRM-only field as a diagnostic, but it is no longer a
        # literal completeness requirement.
        row["fields"] = fields
        missing = [name for name in REQUIRED_FIELDS if not (fields.get(name) or {}).get("ok")]
        row["missing"] = missing
        row["complete"] = not missing
        results.append(row)

    missing_counts = {
        field: sum(1 for row in results if field in row["missing"])
        for field in REQUIRED_FIELDS
    }
    payload = {
        "schema": "avatar-catalog-completeness-v1",
        "generatedAt": legacy.get("generatedAt"),
        "policy": (
            "Every collection research dimension must be resolved. The usable model dimension may be satisfied "
            "by an exhaustive avatar-ready VRM, rigged GLB, or evidence-backed rigged FBX inventory."
        ),
        "summary": {
            "collections": len(results),
            "complete": sum(bool(row["complete"]) for row in results),
            "incomplete": sum(not bool(row["complete"]) for row in results),
            "missingByField": missing_counts,
        },
        "collections": results,
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tiers", default="A,B,C")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    tiers = {part.strip().upper() for part in args.tiers.split(",") if part.strip()}
    payload = run(args.db, args.research, args.inventory, args.output, tiers)
    print(json.dumps(payload["summary"], indent=2))
    return 1 if args.strict and payload["summary"]["incomplete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
