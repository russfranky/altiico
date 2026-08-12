#!/usr/bin/env python3
"""Retain last-good Etherscan contract evidence when a fresh audit is throttled."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def contract_corroborated(evidence: dict[str, Any] | None) -> bool:
    evidence = evidence or {}
    return bool(
        evidence.get("creator")
        or evidence.get("verifiedSource")
        or evidence.get("creationTxHash")
        or evidence.get("eventLogsSampled")
    )


def has_rate_limit_error(item: dict[str, Any]) -> bool:
    return any(
        "rate limit" in str(error).casefold() or "max calls per sec" in str(error).casefold()
        for error in item.get("errors") or []
    )


def same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        str(left.get("chain") or "").casefold() == str(right.get("chain") or "").casefold()
        and str(left.get("contract") or "").casefold() == str(right.get("contract") or "").casefold()
    )


def merge_with_previous(
    fresh: dict[str, Any], previous: dict[str, Any] | None
) -> tuple[dict[str, Any], int]:
    merged = copy.deepcopy(fresh)
    previous_by_id = {
        item.get("catalogId"): item
        for item in (previous or {}).get("collections") or []
        if isinstance(item, dict) and item.get("catalogId")
    }
    preserved = 0
    for item in merged.get("collections") or []:
        if not isinstance(item, dict) or not has_rate_limit_error(item):
            continue
        prior = previous_by_id.get(item.get("catalogId"))
        if not isinstance(prior, dict) or not same_identity(item, prior):
            continue
        fresh_evidence = item.get("contractEvidence") or {}
        prior_evidence = prior.get("contractEvidence") or {}
        if contract_corroborated(fresh_evidence) or not contract_corroborated(prior_evidence):
            continue
        item["contractEvidence"] = copy.deepcopy(prior_evidence)
        item["evidencePreservation"] = {
            "mode": "previous_last_good",
            "reason": (
                "fresh Etherscan observation was rate-limited before corroborated "
                "contract evidence could be recovered"
            ),
            "previousObservedAt": prior.get("observedAt"),
            "freshObservedAt": item.get("observedAt"),
        }
        preserved += 1

    collections = [
        item for item in merged.get("collections") or [] if isinstance(item, dict)
    ]
    summary = dict(merged.get("summary") or {})
    summary["verifiedSourceContracts"] = sum(
        bool((item.get("contractEvidence") or {}).get("verifiedSource"))
        for item in collections
    )
    summary["contractsWithTokenUriAbi"] = sum(
        bool(
            ((item.get("contractEvidence") or {}).get("abiSignals") or {}).get("tokenURI")
            or ((item.get("contractEvidence") or {}).get("abiSignals") or {}).get("uri")
        )
        for item in collections
    )
    summary["preservedCollections"] = preserved
    merged["summary"] = summary
    return merged, preserved


def corroborated_count(report: dict[str, Any]) -> int:
    return sum(
        contract_corroborated((item or {}).get("contractEvidence"))
        for item in report.get("collections") or []
        if isinstance(item, dict)
    )


def rate_limit_error_count(report: dict[str, Any]) -> int:
    return sum(
        has_rate_limit_error(item)
        for item in report.get("collections") or []
        if isinstance(item, dict)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", required=True)
    ap.add_argument("--previous", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--health")
    args = ap.parse_args()

    fresh = json.loads(Path(args.fresh).read_text())
    previous_path = Path(args.previous)
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    selected, preserved = merge_with_previous(fresh, previous)
    inspected = int((fresh.get("summary") or {}).get("collectionsInspected") or 0)
    errored = int((fresh.get("summary") or {}).get("collectionsWithErrors") or 0)
    rate_limited = rate_limit_error_count(fresh)
    fresh_corroborated = corroborated_count(fresh)
    selected_corroborated = corroborated_count(selected)

    if inspected and errored >= inspected and not preserved:
        raise SystemExit(
            "Etherscan refresh errored for every inspected collection and retained "
            "no last-good corroboration"
        )

    Path(args.output).write_text(
        json.dumps(selected, indent=2, ensure_ascii=False) + "\n"
    )
    health = {
        "freshCorroborated": fresh_corroborated,
        "selectedCorroborated": selected_corroborated,
        "rateLimitedCollections": rate_limited,
        "preservedCollections": preserved,
        "mode": "fresh_with_preserved_last_good" if preserved else "fresh",
    }
    if args.health:
        health_path = Path(args.health)
        payload = json.loads(health_path.read_text()) if health_path.exists() else {}
        payload["etherscan"] = health
        health_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        )
    print(json.dumps(health, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
