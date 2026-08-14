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
DEFAULT_OUTPUT = ROOT / "data" / "catalog_research_queue.json"

SOURCE_PLAN = {
    "banner": ["OpenSea collection API", "official project site", "Wayback project/marketplace archive"],
    "logo": ["OpenSea collection API", "official project site", "Wayback project/marketplace archive"],
    "short_description": ["OpenSea collection description", "official project about page", "archived project description"],
    "discord": ["OpenSea collection API", "official site/community page", "official Medium/Mirror", "Wayback archive"],
    "x": ["OpenSea collection API", "official site social links", "historical X account/index", "Wayback archive"],
    "launch_date": ["OpenSea created_date", "contract creation evidence", "contemporaneous mint/drop announcement"],
    "project_status": ["official current site/social activity", "official shutdown/sunset announcement", "Wayback history"],
    "ip_rights": ["official license/terms", "token/VRM metadata license fields", "project repository/docs", "archived terms"],
    "storage": ["enumerated VRM URLs", "tokenURI metadata", "official technical docs"],
    "vrm_inventory": ["Moralis cursor-exhausted collection NFTs", "on-chain tokenURI enumeration", "recursive metadata crawler", "3D Vault/official holder portal"],
    "file_access": ["unauthenticated structural VRM probe", "official download flow", "holder portal / 3D Vault access rules"],
}
PRIORITY = {
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


def run(acceptance_path: Path, output_path: Path) -> dict[str, Any]:
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    queue = []
    for failure in acceptance.get("failures") or []:
        reasons = [str(reason) for reason in failure.get("reasons") or []]
        fields = sorted({category(reason) for reason in reasons})
        queue.append(
            {
                "id": failure.get("id"),
                "name": failure.get("name"),
                "priority": max((PRIORITY.get(field, 50) for field in fields), default=0),
                "missingFields": fields,
                "failureReasons": reasons,
                "researchPlan": {
                    field: SOURCE_PLAN.get(field, ["authoritative project source", "archived source"])
                    for field in fields
                },
            }
        )
    queue.sort(key=lambda row: (-int(row["priority"]), -len(row["missingFields"]), str(row.get("name") or "").lower()))
    payload = {
        "schema": "vrm-catalog-research-queue-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceAcceptanceSchema": acceptance.get("schema"),
        "summary": {
            "collections": len(queue),
            "fieldCounts": {
                field: sum(field in row["missingFields"] for row in queue)
                for field in SOURCE_PLAN
            },
        },
        "queue": queue,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run(args.acceptance, args.output)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
