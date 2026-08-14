#!/usr/bin/env python3
"""Enforce the literal full-catalog acceptance bar.

Identity/media/social fields need actual values. Non-terminal collections need
explicit exhaustive VRM links, every link must structurally probe as a VRM, and
storage/access/IP/lifecycle facts must be resolved. URL templates and sampled
links are not accepted as substitutes for the explicit inventory.

The final gate also checks the curated markdown catalog as an independent scope
source. A collection cannot disappear from the DB-derived completeness report
and thereby escape the acceptance denominator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.reconcile_markdown_catalog_sources import collection_leads, normalize_name
except ModuleNotFoundError:  # direct `python scripts/...` execution
    from reconcile_markdown_catalog_sources import collection_leads, normalize_name

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = ROOT / "data" / "catalog_completeness_report.json"
DEFAULT_INVENTORY = ROOT / "static" / "data" / "vrm-inventory.json"
DEFAULT_PROBE = ROOT / "data" / "vrm_inventory_probe.json"
DEFAULT_SCOPE_SOURCE = ROOT / "data" / "vrm_collections.md"

MUST_HAVE_VALUE = (
    "banner",
    "short_description",
    "discord",
    "x",
    "logo",
    "launch_date",
)
TERMINAL_INVENTORY_STATES = {"not_shipped", "unrecoverable"}
PROJECT_STATUSES = {"active", "dormant", "sunset"}
SCOPE_TIERS = {"A", "B", "C", "ARWEAVE"}


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
        failures.append("storage:inventory_storage_required")
        failures.append("vrm_inventory:inventory_record_required")
        failures.append("file_access:inventory_access_record_required")
        return failures

    storage_info = inventory.get("storage") or {}
    if not has(storage_info.get("types")):
        failures.append("storage:actual_storage_type_required")

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


def scope_omissions(
    collections: list[dict[str, Any]], source_path: Path
) -> tuple[int, list[dict[str, Any]]]:
    """Return curated in-scope collection count and identities absent from report."""
    leads = [
        lead
        for lead in collection_leads(source_path.read_text(encoding="utf-8"))
        if str(lead.get("tier") or "").strip().upper() in SCOPE_TIERS
    ]
    report_ids = {
        str(row.get("id") or "").strip().lower()
        for row in collections
        if str(row.get("id") or "").strip()
    }
    report_names = {
        normalize_name(row.get("name"))
        for row in collections
        if normalize_name(row.get("name"))
    }

    missing: list[dict[str, Any]] = []
    for lead in leads:
        lead_id = str(lead.get("id") or "").strip().lower()
        lead_name = normalize_name(lead.get("name"))
        if (lead_id and lead_id in report_ids) or (lead_name and lead_name in report_names):
            continue
        missing.append(
            {
                "id": lead.get("id"),
                "name": lead.get("name"),
                "reasons": ["catalog_scope:missing_from_completeness_report"],
                "scope": {
                    "tier": lead.get("tier"),
                    "contract": lead.get("contract"),
                    "source_section": lead.get("source_section"),
                    "source_line": lead.get("source_line"),
                },
            }
        )
    return len(leads), missing


def run(
    report_path: Path,
    inventory_path: Path,
    probe_path: Path | None = None,
    scope_source_path: Path | None = None,
) -> dict[str, Any]:
    report = load(report_path)
    report_collections = [
        row for row in report.get("collections") or [] if isinstance(row, dict)
    ]
    inventories = inventory_index(load(inventory_path))
    probes = probe_index(load(probe_path)) if probe_path and probe_path.exists() else {}

    failures: list[dict[str, Any]] = []
    for collection in report_collections:
        cid = str(collection.get("id") or "")
        reasons = evaluate_collection(collection, inventories.get(cid), probes.get(cid))
        if reasons:
            failures.append({"id": cid, "name": collection.get("name"), "reasons": reasons})

    source_collection_count: int | None = None
    scope_missing: list[dict[str, Any]] = []
    if scope_source_path is not None:
        source_collection_count, scope_missing = scope_omissions(
            report_collections, scope_source_path
        )
        failures.extend(scope_missing)

    reason_counts: dict[str, int] = {}
    for row in failures:
        for reason in row["reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    denominator = len(report_collections) + len(scope_missing)
    result = {
        "schema": "vrm-catalog-acceptance-v3",
        "collections": denominator,
        "reportCollections": len(report_collections),
        "scopeCollections": source_collection_count,
        "scopeMissing": len(scope_missing),
        "passing": denominator - len(failures),
        "failing": len(failures),
        "reasonCounts": dict(
            sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "failures": failures,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--scope-source", type=Path, default=DEFAULT_SCOPE_SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run(args.report, args.inventory, args.probe, args.scope_source)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "collections",
                    "reportCollections",
                    "scopeCollections",
                    "scopeMissing",
                    "passing",
                    "failing",
                    "reasonCounts",
                )
            },
            indent=2,
        )
    )
    return 1 if result["failing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
