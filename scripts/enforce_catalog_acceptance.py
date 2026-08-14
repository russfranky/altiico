#!/usr/bin/env python3
"""Enforce the literal full-catalog acceptance bar.

Required identity/media/social fields need actual values. For active/dormant
collections with files, the inventory needs explicit exhaustive VRM links and
every link must have passed the lightweight structural VRM probe. An unexpanded
URL template is not "all links".

Only evidence-backed ``not_shipped`` and ``unrecoverable`` inventory states can
complete without URLs. Holder-gated files still exist and therefore still need
an explicit inventory plus ownership/access facts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = ROOT / "data" / "catalog_completeness_report.json"
DEFAULT_INVENTORY = ROOT / "static" / "data" / "vrm-inventory.json"
DEFAULT_PROBE = ROOT / "data" / "vrm_inventory_probe.json"

MUST_HAVE_VALUE = (
    "banner",
    "short_description",
    "discord",
    "x",
    "logo",
    "launch_date",
    "storage",
)
TERMINAL_INVENTORY_STATES = {"not_shipped", "unrecoverable"}
PROJECT_STATUSES = {"active", "dormant", "sunset"}


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


def probe_index(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    return {
        str(row.get("catalogId")): row
        for row in payload.get("collections") or []
        if isinstance(row, dict) and row.get("catalogId")
    }


def field_has_value(field: dict[str, Any]) -> bool:
    return bool(field.get("ok")) and has(field.get("value"))


def evaluate_collection(
    collection: dict[str, Any],
    inventory: dict[str, Any] | None,
    probe: dict[str, Any] | None = None,
) -> list[str]:
    failures: list[str] = []
    fields = collection.get("fields") or {}

    for name in MUST_HAVE_VALUE:
        field = fields.get(name) or {}
        if not field_has_value(field):
            failures.append(f"{name}:actual_value_required")

    status = fields.get("project_status") or {}
    status_value = str(status.get("value") or "").strip().lower()
    if not status.get("ok") or status_value not in PROJECT_STATUSES:
        failures.append("project_status:evidenced_status_required")

    rights = fields.get("ip_rights") or {}
    if not rights.get("ok") or not has(rights.get("value")):
        failures.append("ip_rights:researched_information_required")

    if not inventory:
        failures.append("vrm_inventory:inventory_record_required")
        failures.append("file_access:inventory_access_record_required")
        return failures

    inv_state = str(inventory.get("state") or "").strip().lower()
    inv_evidence = inventory.get("inventory_evidence") or []
    urls = inventory.get("urls") or []

    if inv_state == "complete":
        if not inventory.get("complete"):
            failures.append("vrm_inventory:complete_flag_required")
        if not urls:
            failures.append("vrm_inventory:exhaustive_urls_required")
        if not probe or not probe.get("structurallyComplete"):
            failures.append("vrm_inventory:all_links_must_probe_as_vrm")
    elif inv_state in TERMINAL_INVENTORY_STATES:
        if not inventory.get("complete") or not inv_evidence:
            failures.append("vrm_inventory:terminal_state_requires_evidence")
    else:
        failures.append("vrm_inventory:explicit_exhaustive_links_required")

    access = inventory.get("access") or {}
    mode = str(access.get("mode") or "").strip().lower()
    requires_ownership = access.get("requires_ownership")
    access_evidence = access.get("evidence") or []

    if inv_state in TERMINAL_INVENTORY_STATES and mode == "unavailable":
        if not access_evidence:
            failures.append("file_access:unavailable_requires_evidence")
    else:
        if mode not in {"public", "holder_gated", "account_gated"}:
            failures.append("file_access:explicit_access_mode_required")
        if not isinstance(requires_ownership, bool):
            failures.append("file_access:ownership_requirement_boolean_required")
        if mode == "holder_gated" and requires_ownership is not True:
            failures.append("file_access:holder_gated_must_require_ownership")
        if mode == "public" and requires_ownership is not False:
            failures.append("file_access:public_must_not_require_ownership")

    return failures


def run(
    report_path: Path,
    inventory_path: Path,
    probe_path: Path | None = None,
) -> dict[str, Any]:
    report = load(report_path)
    inventories = inventory_index(load(inventory_path))
    probes = probe_index(load(probe_path)) if probe_path and probe_path.exists() else {}

    failures: list[dict[str, Any]] = []
    for collection in report.get("collections") or []:
        cid = str(collection.get("id") or "")
        reasons = evaluate_collection(
            collection,
            inventories.get(cid),
            probes.get(cid),
        )
        if reasons:
            failures.append(
                {
                    "id": cid,
                    "name": collection.get("name"),
                    "reasons": reasons,
                }
            )

    reason_counts: dict[str, int] = {}
    for row in failures:
        for reason in row["reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "schema": "vrm-catalog-acceptance-v2",
        "collections": len(report.get("collections") or []),
        "passing": len(report.get("collections") or []) - len(failures),
        "failing": len(failures),
        "reasonCounts": dict(
            sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run(args.report, args.inventory, args.probe)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("collections", "passing", "failing", "reasonCounts")
            },
            indent=2,
        )
    )
    return 1 if result["failing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
