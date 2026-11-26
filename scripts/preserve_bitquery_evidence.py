#!/usr/bin/env python3
"""Retain last-good Bitquery evidence when a fresh audit observes nothing."""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLACEHOLDER = {
    "schema": "bitquery-nft-evidence-v1",
    "availability": "unavailable",
    "reason": (
        "latest Bitquery attempt produced no on-chain observations and no "
        "healthy last-good snapshot exists"
    ),
    "policy": (
        "optional independent corroboration; Etherscan remains the required "
        "on-chain source"
    ),
    "summary": {
        "collectionsInspected": 0,
        "collectionsObservedOnchain": 0,
        "collectionsWithErrors": 0,
        "tokensSampled": 0,
        "transferUris": 0,
        "modelSignalTokens": 0,
    },
    "collections": [],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def summary_of(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    summary = report.get("summary")
    return dict(summary) if isinstance(summary, dict) else {}


def observed_count(report: dict[str, Any] | None) -> int:
    return int(summary_of(report).get("collectionsObservedOnchain") or 0)


def inspected_count(report: dict[str, Any] | None) -> int:
    return int(summary_of(report).get("collectionsInspected") or 0)


def error_count(report: dict[str, Any] | None) -> int:
    return int(summary_of(report).get("collectionsWithErrors") or 0)


def fresh_usable(report: dict[str, Any] | None) -> bool:
    return observed_count(report) > 0


def last_good(report: dict[str, Any] | None) -> bool:
    return observed_count(report) > 0


def placeholder_report() -> dict[str, Any]:
    payload = copy.deepcopy(PLACEHOLDER)
    payload["generatedAt"] = now_iso()
    return payload


def select_report(
    fresh: dict[str, Any] | None, previous: dict[str, Any] | None
) -> tuple[dict[str, Any], str]:
    if fresh_usable(fresh):
        return fresh or {}, "fresh"
    if last_good(previous):
        return previous or {}, "previous_last_good"
    return placeholder_report(), "unavailable"


def _read_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", required=True)
    ap.add_argument("--previous", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--health")
    args = ap.parse_args(argv)

    fresh_path = Path(args.fresh)
    previous_path = Path(args.previous)
    fresh = _read_json_dict(fresh_path)
    previous = _read_json_dict(previous_path)
    selected, mode = select_report(fresh, previous)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(selected, indent=2, ensure_ascii=False) + "\n")

    health = {
        "freshObservations": observed_count(fresh),
        "freshErrors": error_count(fresh),
        "freshInspected": inspected_count(fresh),
        "selectedObservations": observed_count(selected),
        "mode": mode,
        "attemptSummary": summary_of(fresh),
    }
    if args.health:
        health_path = Path(args.health)
        health_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _read_json_dict(health_path) or {}
        payload["bitquery"] = health
        health_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(health, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
