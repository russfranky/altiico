#!/usr/bin/env python3
"""Turn literal acceptance failures into a source-specific research queue."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ACCEPTANCE = ROOT / "data" / "catalog_acceptance.json"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research_merged.json"
DEFAULT_OUTPUT = ROOT / "data" / "catalog_research_queue.json"

SOURCE_PLAN = {
    "banner": ["OpenSea collection API", "official project site", "Wayback project/marketplace archive"],
    "logo": ["OpenSea collection API", "official project site", "Wayback project/marketplace archive"],
    "short_description": ["OpenSea collection description", "official project about page", "archived project description"],
    "discord": ["OpenSea collection API", "official site/community page", "official Medium/Mirror", "Wayback archive"],
    "x": ["OpenSea collection API", "official site social links", "historical X account/index", "Wayback archive"],
    "launch_date": ["OpenSea created_date", "contract creation evidence", "contemporaneous mint/drop announcement"],
    "project_status": ["official current site/social activity", "official shutdown/sunset announcement", "Wayback history"],
    "ip_rights": ["official license/terms", "token/model metadata license fields", "project repository/docs", "archived terms"],
    "storage": ["enumerated avatar URLs", "tokenURI metadata", "official technical docs", "OpenPage/MML model references"],
    "avatar_inventory": [
        "OpenPage avatar records and MML model references",
        "Moralis cursor-exhausted VRM metadata",
        "on-chain tokenURI enumeration",
        "recursive project/release repository search for VRM/GLB/FBX",
        "official holder portal / 3D Vault",
        "archived avatar interoperability registries",
    ],
    "vrm_inventory": [
        "Moralis cursor-exhausted collection NFTs",
        "on-chain tokenURI enumeration",
        "recursive metadata crawler",
        "3D Vault/official holder portal",
    ],
    "file_access": [
        "unauthenticated avatar asset probe",
        "official download flow",
        "holder portal / 3D Vault access rules",
    ],
}
PRIORITY = {
    "avatar_inventory": 100,
    "vrm_inventory": 100,
    "file_access": 95,
    "project_status": 90,
    "ip_rights": 85,
    "banner": 80,
    "logo": 80,
    "discord": 75,
    "x": 75,
    "launch_date": 70,
    "short_description": 65,
    "storage": 60,
}


def category(reason: str) -> str:
    prefix = reason.split(":", 1)[0]
    if prefix in SOURCE_PLAN:
        return prefix
    return prefix


def load_research(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    collections = payload.get("collections") if isinstance(payload, dict) else None
    if not isinstance(collections, dict):
        return {}
    return {
        str(collection_id): row
        for collection_id, row in collections.items()
        if isinstance(row, dict)
    }


def text(value: Any) -> str:
    return str(value or "").strip()


def field_state(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if not isinstance(value, dict):
        return None
    state = text(value.get("state") or value.get("coverage"))
    return state or None


def field_values(row: dict[str, Any], key: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, dict):
        return []
    raw = value.get("value")
    if isinstance(raw, list):
        return [text(item) for item in raw if text(item)]
    return [text(raw)] if text(raw) else []


def avatar_research_context(row: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key in (
        "avatar_inventory",
        "avatar_format_leads",
        "avatar_formats",
        "historical_3d_avatar_development",
        "historical_avatar_development",
        "platform_avatar_inventory",
        "streaming_avatar_lane",
    ):
        state = field_state(row, key)
        if state:
            context[key] = state
    formats = field_values(row, "avatar_format_leads") or field_values(row, "avatar_formats")
    if formats:
        context["known_formats"] = formats
    access = row.get("avatar_file_access") or row.get("source_3d_file_access") or row.get("file_access")
    if isinstance(access, dict):
        mode = text(access.get("mode") or access.get("value"))
        if mode:
            context["access_mode"] = mode
        if access.get("requires_ownership") is not None:
            context["requires_ownership"] = bool(access.get("requires_ownership"))
    return context


def avatar_plan(row: dict[str, Any]) -> list[str]:
    """Prioritize the unresolved step implied by evidence already in research."""
    plan: list[str] = []
    inventory = row.get("avatar_inventory") if isinstance(row.get("avatar_inventory"), dict) else {}
    inventory_state = text(inventory.get("state") or inventory.get("coverage")).lower()
    lead = row.get("avatar_format_leads") if isinstance(row.get("avatar_format_leads"), dict) else {}
    lead_state = text(lead.get("state") or lead.get("coverage")).lower()
    formats = field_values(row, "avatar_format_leads") or field_values(row, "avatar_formats")
    format_text = "/".join(fmt.upper() for fmt in formats)

    if inventory_state == "shipped_unenumerated":
        plan.append(
            "recover the known holder/public avatar delivery surface and exhaustively enumerate every supported model file"
        )
    if "portal" in lead_state and "unverified" in lead_state:
        label = f" for reported {format_text} assets" if format_text else ""
        plan.append(
            "recover and verify the reported 3D download portal"
            + label
            + "; capture direct URLs, ownership requirements, and collection coverage"
        )
    if row.get("platform_avatar_inventory"):
        plan.append(
            "trace the complete platform-avatar set back to an export/download API or source package in VRM, rigged GLB, or evidence-backed rigged FBX"
        )
    if row.get("historical_3d_avatar_development") or row.get("historical_avatar_development"):
        plan.append(
            "search final release announcements, archived holder portals, repositories, and Wayback snapshots for the documented 3D production program"
        )
    if row.get("streaming_avatar_lane"):
        plan.append(
            "keep streaming/video-avatar rigs separate from 3D files; only promote if an underlying downloadable VRM, rigged GLB, or rigged FBX is evidenced"
        )

    access = row.get("avatar_file_access") or row.get("source_3d_file_access") or row.get("file_access")
    if isinstance(access, dict) and access.get("requires_ownership") is True:
        plan.append(
            "inspect the holder-gated flow without treating authentication as absence; record portal URL and enumerate the holder-specific model mapping"
        )

    # Keep the generic high-recall sources after the evidence-specific actions.
    for source in SOURCE_PLAN["avatar_inventory"]:
        if source not in plan:
            plan.append(source)
    return plan


def plan_for(field: str, research_row: dict[str, Any]) -> list[str]:
    if field == "avatar_inventory" and research_row:
        return avatar_plan(research_row)
    return SOURCE_PLAN.get(field, ["authoritative project source", "archived source"])


def run(
    acceptance_path: Path,
    output_path: Path,
    research_path: Path | None = None,
) -> dict[str, Any]:
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    research = load_research(research_path)
    queue = []
    for failure in acceptance.get("failures") or []:
        reasons = [str(reason) for reason in failure.get("reasons") or []]
        fields = sorted({category(reason) for reason in reasons})
        collection_id = text(failure.get("id"))
        research_row = research.get(collection_id) or {}
        row = {
            "id": failure.get("id"),
            "name": failure.get("name"),
            "priority": max((PRIORITY.get(field, 50) for field in fields), default=0),
            "missingFields": fields,
            "failureReasons": reasons,
            "researchPlan": {
                field: plan_for(field, research_row)
                for field in fields
            },
        }
        context = avatar_research_context(research_row) if "avatar_inventory" in fields else {}
        if context:
            row["researchContext"] = context
        queue.append(row)
    queue.sort(
        key=lambda row: (
            -int(row["priority"]),
            -len(row["missingFields"]),
            str(row.get("name") or "").lower(),
        )
    )
    payload = {
        "schema": "avatar-catalog-research-queue-v3",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceAcceptanceSchema": acceptance.get("schema"),
        "sourceResearch": str(research_path) if research_path else None,
        "summary": {
            "collections": len(queue),
            "fieldCounts": {
                field: sum(field in row["missingFields"] for row in queue)
                for field in SOURCE_PLAN
            },
            "evidenceAwareAvatarPlans": sum(
                bool(row.get("researchContext")) for row in queue
            ),
        },
        "queue": queue,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--research", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args.acceptance, args.output, args.research)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
