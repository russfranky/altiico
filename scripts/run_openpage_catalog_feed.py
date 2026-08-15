#!/usr/bin/env python3
"""Run the complete OpenPage-to-avatar-inventory lane outside GitHub Actions.

This command exists because the repository's hosted Actions jobs may fail before
checkout. It uses only the OpenPage credential plus committed catalog data, so a
maintainer can execute the exact productive lane from any checkout:

1. build merged catalog research identities;
2. exhaust OpenPage communities;
3. discover current community asset-list routes from OpenAPI and enumerate them;
4. bind records only by curated OpenPage ID or unique catalog contract;
5. resolve MML/VRM/model-GLB candidates;
6. merge candidates into the broader avatar inventory and structurally probe it;
7. emit an explicit health report and reject a nonproductive feed by default.

The command does not commit or push files. It never treats MML, animation GLBs,
or unbound records as usable avatar inventory.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMMUNITIES = ROOT / "data" / "openpage_communities.json"
DEFAULT_COMMUNITY_ASSETS = ROOT / "data" / "openpage_community_assets.json"
DEFAULT_DISCOVERY = ROOT / "data" / "openpage_asset_discovery.json"
DEFAULT_HEALTH = ROOT / "data" / "openpage_feed_health.json"
DEFAULT_RESEARCH = ROOT / "data" / "catalog_research_merged.json"
DEFAULT_BINDINGS = ROOT / "data" / "openpage_catalog_bindings.json"
DEFAULT_SOURCES = ROOT / "data" / "openpage_asset_sources.json"
DEFAULT_VRM_INVENTORY = ROOT / "static" / "data" / "vrm-inventory.json"
DEFAULT_AVATAR_INVENTORY = ROOT / "static" / "data" / "avatar-inventory.json"
DEFAULT_PROBE = ROOT / "data" / "avatar_inventory_probe.json"


def text(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return fallback or {}
    return payload


def command(args: Sequence[str], *, env: dict[str, str] | None = None) -> None:
    printable = " ".join(args)
    print(f"+ {printable}", flush=True)
    subprocess.run(
        list(args),
        cwd=ROOT,
        env=env,
        check=True,
    )


def candidate_urls(row: dict[str, Any], field: str) -> set[str]:
    urls: set[str] = set()
    hits = row.get(field)
    if not isinstance(hits, list):
        return urls
    for hit in hits:
        if isinstance(hit, str):
            value = text(hit)
        elif isinstance(hit, dict):
            value = text(hit.get("url"))
        else:
            value = ""
        if value:
            urls.add(value)
    return urls


def build_health(
    communities: dict[str, Any],
    community_assets: dict[str, Any],
    discovery: dict[str, Any],
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    community_summary = communities.get("summary")
    if not isinstance(community_summary, dict):
        community_summary = {}
    source_summary = community_assets.get("summary")
    if not isinstance(source_summary, dict):
        source_summary = {}
    binding_summary = discovery.get("bindingSummary")
    if not isinstance(binding_summary, dict):
        binding_summary = {}
    records = discovery.get("records")
    if not isinstance(records, list):
        records = []
    rows = [row for row in records if isinstance(row, dict)]
    bound_asset_rows = [
        row
        for row in rows
        if text(row.get("catalogId"))
        and (candidate_urls(row, "vrmCandidates") or candidate_urls(row, "glbUrls"))
    ]
    bound_vrms = {
        url for row in bound_asset_rows for url in candidate_urls(row, "vrmCandidates")
    }
    bound_glbs = {
        url for row in bound_asset_rows for url in candidate_urls(row, "glbUrls")
    }

    probe_summary: dict[str, Any] = {}
    if isinstance(probe, dict) and isinstance(probe.get("summary"), dict):
        probe_summary = dict(probe["summary"])

    return {
        "schema": "openpage-feed-health-v3",
        "communitiesEnumerated": int(community_summary.get("communitiesEnumerated") or 0),
        "communityCoverageComplete": community_summary.get("coverageComplete") is True,
        "assetListEndpoints": int(source_summary.get("endpoints") or 0),
        "assetListRequestsSucceeded": int(source_summary.get("requestsSucceeded") or 0),
        "assetListRequestsFailed": int(source_summary.get("requestsFailed") or 0),
        "assetListItems": int(source_summary.get("items") or 0),
        "assetListCatalogBoundItems": int(source_summary.get("catalogBoundItems") or 0),
        "assetListCoverageComplete": source_summary.get("coverageComplete") is True,
        "records": len(rows),
        "boundRecords": int(binding_summary.get("bound") or 0),
        "boundAssetRecords": len(bound_asset_rows),
        "boundVrmCandidates": len(bound_vrms),
        "boundGlbCandidates": len(bound_glbs),
        "probeSummary": probe_summary,
        "productive": bool(bound_vrms or bound_glbs),
    }


def validate_community_report(payload: dict[str, Any]) -> None:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeError("OpenPage community report has no summary")
    count = int(summary.get("communitiesEnumerated") or 0)
    if count <= 0:
        raise RuntimeError("OpenPage returned zero communities")
    if summary.get("coverageComplete") is not True:
        raise RuntimeError("OpenPage community pagination is incomplete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default=os.environ.get("OPENPAGE_API_KEY", ""))
    parser.add_argument(
        "--api-base",
        default=os.environ.get("OPENPAGE_API_BASE", "https://api.openpage.fun/v1"),
    )
    parser.add_argument("--openapi-url", action="append", default=[])
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument(
        "--allow-unproductive",
        action="store_true",
        help="Write evidence and return success even when no bound VRM/GLB candidate is found",
    )
    args = parser.parse_args()

    api_key = text(args.api_key)
    if not api_key:
        raise SystemExit("OPENPAGE_API_KEY or --api-key is required")
    env = dict(os.environ)
    env["OPENPAGE_API_KEY"] = api_key
    env["OPENPAGE_API_BASE"] = args.api_base
    python = sys.executable

    command(
        [
            python,
            "scripts/build_catalog_research_store.py",
            "--output",
            str(DEFAULT_RESEARCH.relative_to(ROOT)),
        ],
        env=env,
    )
    command(
        [
            python,
            "scripts/discover_openpage_communities.py",
            "--api-base",
            args.api_base,
            "--api-key",
            api_key,
            "--per-page",
            str(max(1, args.per_page)),
            "--max-pages",
            str(max(0, args.max_pages)),
            "--output",
            str(DEFAULT_COMMUNITIES.relative_to(ROOT)),
        ],
        env=env,
    )
    communities = load_json(DEFAULT_COMMUNITIES)
    validate_community_report(communities)

    asset_command = [
        python,
        "scripts/discover_openpage_community_assets.py",
        "--communities",
        str(DEFAULT_COMMUNITIES.relative_to(ROOT)),
        "--bindings",
        str(DEFAULT_BINDINGS.relative_to(ROOT)),
        "--output",
        str(DEFAULT_COMMUNITY_ASSETS.relative_to(ROOT)),
        "--api-base",
        args.api_base,
        "--api-key",
        api_key,
        "--per-page",
        str(max(1, args.per_page)),
        "--max-pages",
        str(max(0, args.max_pages)),
    ]
    for url in args.openapi_url:
        asset_command.extend(["--openapi-url", url])
    command(asset_command, env=env)

    command(
        [
            python,
            "scripts/build_openpage_catalog_feed.py",
            "--research",
            str(DEFAULT_RESEARCH.relative_to(ROOT)),
            "--bindings",
            str(DEFAULT_BINDINGS.relative_to(ROOT)),
            "--input",
            str(DEFAULT_COMMUNITIES.relative_to(ROOT)),
            "--input",
            str(DEFAULT_COMMUNITY_ASSETS.relative_to(ROOT)),
            "--input",
            str(DEFAULT_SOURCES.relative_to(ROOT)),
            "--output",
            str(DEFAULT_DISCOVERY.relative_to(ROOT)),
            "--fetch-mml",
            "--strict-source-fetch",
        ],
        env=env,
    )
    command(
        [
            python,
            "scripts/export_avatar_inventory.py",
            "--research",
            str(DEFAULT_RESEARCH.relative_to(ROOT)),
            "--vrm-inventory",
            str(DEFAULT_VRM_INVENTORY.relative_to(ROOT)),
            "--openpage-assets",
            str(DEFAULT_DISCOVERY.relative_to(ROOT)),
            "--output",
            str(DEFAULT_AVATAR_INVENTORY.relative_to(ROOT)),
        ],
        env=env,
    )

    probe: dict[str, Any] = {}
    if not args.skip_probe:
        command(
            [
                python,
                "scripts/probe_avatar_inventory.py",
                "--source",
                str(DEFAULT_AVATAR_INVENTORY.relative_to(ROOT)),
                "--output",
                str(DEFAULT_PROBE.relative_to(ROOT)),
                "--workers",
                str(max(1, args.workers)),
                "--timeout",
                str(max(1.0, args.timeout)),
            ],
            env=env,
        )
        probe = load_json(DEFAULT_PROBE)

    health = build_health(
        communities,
        load_json(DEFAULT_COMMUNITY_ASSETS),
        load_json(DEFAULT_DISCOVERY),
        probe,
    )
    DEFAULT_HEALTH.write_text(json.dumps(health, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(health, indent=2))
    if not health["productive"] and not args.allow_unproductive:
        print(
            "OpenPage produced no explicitly catalog-bound VRM or model-GLB candidates.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
