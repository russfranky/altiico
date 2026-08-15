#!/usr/bin/env python3
"""Enumerate OpenPage communities as high-recall catalog research leads.

The current documented API base is ``https://api.openpage.fun/v1``. The base
URL remains configurable through ``OPENPAGE_API_BASE`` or ``--api-base`` so a
future host migration does not require code changes.

Community results contain useful research fields such as description, X,
Discord, website and logo. They are emitted as source evidence only. This script
never attaches a community to a catalog collection by display-name similarity;
identity binding must use explicit curator/source evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "openpage_communities.json"
DEFAULT_API_BASE = os.environ.get(
    "OPENPAGE_API_BASE", "https://api.openpage.fun/v1"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any) -> str:
    return str(value or "").strip()


def request_json(url: str, api_key: str, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "vrm-catalog-openpage-community-discovery/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"OpenPage response from {url} must be an object")
    return payload


def community_page_url(api_base: str, page: int, per_page: int) -> str:
    query = urllib.parse.urlencode({"page": page, "perPage": per_page})
    return f"{api_base.rstrip('/')}/community?{query}"


def collect_communities(
    *,
    api_base: str,
    api_key: str,
    per_page: int = 100,
    max_pages: int = 0,
    requester: Callable[[str, str], dict[str, Any]] = request_json,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page = 1
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pages = 0
    total_reported: int | None = None
    truncated = False

    while True:
        payload = requester(community_page_url(api_base, page, per_page), api_key)
        pages += 1
        raw_total = payload.get("total")
        try:
            total_reported = (
                int(raw_total) if raw_total is not None else total_reported
            )
        except (TypeError, ValueError):
            pass

        rows = payload.get("results") or []
        if not isinstance(rows, list):
            raise ValueError("OpenPage community response `results` must be a list")
        new_rows = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            community_id = text(row.get("id"))
            dedupe_key = community_id or json.dumps(
                row, sort_keys=True, ensure_ascii=False
            )
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            results.append(row)
            new_rows += 1

        if max_pages and pages >= max_pages:
            if total_reported is None or len(results) < total_reported:
                truncated = True
            break
        if total_reported is not None and len(results) >= total_reported:
            break
        if not rows or new_rows == 0 or len(rows) < per_page:
            break
        page += 1

    coverage_complete = not truncated and (
        total_reported is None or len(results) >= total_reported
    )
    return results, {
        "pages": pages,
        "totalReported": total_reported,
        "communitiesEnumerated": len(results),
        "truncated": truncated,
        "coverageComplete": coverage_complete,
    }


def normalize_community(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "openpageId": row.get("id"),
        "name": row.get("name"),
        "shortName": row.get("shortName"),
        "description": row.get("description"),
        "x": row.get("twitter"),
        "discord": row.get("discord"),
        "youtube": row.get("youtube"),
        "website": row.get("website"),
        "logo": row.get("logo"),
        "type": row.get("type"),
        "requestLevel": row.get("requestLevel"),
        "approvedAt": row.get("approvedAt"),
        "verifiedAt": row.get("verifiedAt"),
        "createdAt": row.get("createdAt"),
        "updatedAt": row.get("updatedAt"),
        "catalogId": None,
        "bindingState": "unbound",
    }


def build_report(
    communities: list[dict[str, Any]],
    coverage: dict[str, Any],
    *,
    api_base: str,
) -> dict[str, Any]:
    normalized = [normalize_community(row) for row in communities]
    return {
        "schema": "openpage-community-discovery-v1",
        "generatedAt": now_iso(),
        "source": {
            "name": "OpenPage",
            "apiBase": api_base.rstrip("/"),
            "endpoint": "/community",
        },
        "policy": (
            "OpenPage community metadata is a high-recall source for descriptions, socials, websites and logos. "
            "Community display names never create catalog identity bindings by themselves; catalogId remains null "
            "until an explicit contract/collection/source mapping is established."
        ),
        "summary": {
            **coverage,
            "withDescription": sum(
                bool(text(row.get("description"))) for row in normalized
            ),
            "withX": sum(bool(text(row.get("x"))) for row in normalized),
            "withDiscord": sum(
                bool(text(row.get("discord"))) for row in normalized
            ),
            "withWebsite": sum(
                bool(text(row.get("website"))) for row in normalized
            ),
            "withLogo": sum(bool(text(row.get("logo"))) for row in normalized),
        },
        "communities": normalized,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument(
        "--api-key", default=os.environ.get("OPENPAGE_API_KEY", "")
    )
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument(
        "--max-pages", type=int, default=0, help="0 = exhaust pagination"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not text(args.api_key):
        raise SystemExit("OPENPAGE_API_KEY or --api-key is required")
    communities, coverage = collect_communities(
        api_base=args.api_base,
        api_key=args.api_key,
        per_page=max(1, args.per_page),
        max_pages=max(0, args.max_pages),
    )
    report = build_report(communities, coverage, api_base=args.api_base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
