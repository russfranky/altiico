#!/usr/bin/env python3
"""Print a concise status summary from committed Altiico Catalog artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class StatusError(RuntimeError):
    """Raised when a required status artifact is missing or malformed."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StatusError(f"required artifact is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StatusError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StatusError(f"expected a JSON object in {path}")
    return value


def number(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StatusError(f"expected integer for {label}, got {value!r}")
    return value


def build_status(root: Path) -> dict[str, Any]:
    acceptance = load_json(root / "data" / "catalog_acceptance.json")
    staging = load_json(root / "static" / "data" / "hubzz-prealpha-staging.json")
    build_info = load_json(root / "static" / "data" / "build-info.json")

    collections = number(acceptance.get("collections"), "acceptance.collections")
    passing = number(acceptance.get("passing"), "acceptance.passing")
    failing = number(acceptance.get("failing"), "acceptance.failing")
    scope_missing = number(acceptance.get("scopeMissing", 0), "acceptance.scopeMissing")
    report_collections = number(
        acceptance.get("reportCollections", 0), "acceptance.reportCollections"
    )

    summary = staging.get("summary")
    if not isinstance(summary, dict):
        raise StatusError("staging.summary must be an object")

    catalog_sets = number(summary.get("catalogSets"), "staging.summary.catalogSets")
    stageable_sets = number(summary.get("stageableSets"), "staging.summary.stageableSets")
    deferred_sets = number(summary.get("deferredSets"), "staging.summary.deferredSets")
    source_avatars = number(summary.get("sourceAvatars"), "staging.summary.sourceAvatars")
    binary_avatars = number(
        summary.get("binaryValidatedSourceAvatars"),
        "staging.summary.binaryValidatedSourceAvatars",
    )

    if passing + failing != collections:
        raise StatusError("acceptance passing and failing counts do not equal collections")
    if stageable_sets + deferred_sets != catalog_sets:
        raise StatusError("staging stageable and deferred counts do not equal catalog sets")

    return {
        "snapshot_id": build_info.get("snapshot_id"),
        "public_generated_at": build_info.get("generated_at"),
        "market_data_as_of": build_info.get("market_data_as_of"),
        "acceptance": {
            "collections": collections,
            "passing": passing,
            "failing": failing,
            "passing_percent": round((passing / collections * 100) if collections else 0.0, 1),
            "report_collections": report_collections,
            "scope_missing": scope_missing,
        },
        "staging": {
            "catalog_sets": catalog_sets,
            "stageable_sets": stageable_sets,
            "deferred_sets": deferred_sets,
            "stageable_percent": round(
                (stageable_sets / catalog_sets * 100) if catalog_sets else 0.0, 1
            ),
            "source_avatars": source_avatars,
            "binary_validated_source_avatars": binary_avatars,
        },
    }


def print_text(status: dict[str, Any]) -> None:
    acceptance = status["acceptance"]
    staging = status["staging"]
    print("Altiico Catalog status")
    print(f"Snapshot: {status.get('snapshot_id') or 'unknown'}")
    print(f"Public build generated: {status.get('public_generated_at') or 'unknown'}")
    print(f"Market data as of: {status.get('market_data_as_of') or 'unknown'}")
    print(
        "Acceptance: "
        f"{acceptance['passing']}/{acceptance['collections']} passing "
        f"({acceptance['passing_percent']:.1f}%), "
        f"{acceptance['failing']} failing"
    )
    print(
        "Completeness report: "
        f"{acceptance['report_collections']} collections, "
        f"{acceptance['scope_missing']} scope entries missing"
    )
    print(
        "Hubzz staging: "
        f"{staging['stageable_sets']}/{staging['catalog_sets']} stageable "
        f"({staging['stageable_percent']:.1f}%), "
        f"{staging['deferred_sets']} deferred"
    )
    print(
        "Source avatars: "
        f"{staging['binary_validated_source_avatars']}/"
        f"{staging['source_avatars']} binary-validated"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root, default: inferred from this script",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    try:
        status = build_status(args.root.resolve())
    except StatusError as exc:
        print(f"status error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print_text(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
