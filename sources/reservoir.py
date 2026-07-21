#!/usr/bin/env python3
"""Reservoir API source: EVM candidate discovery + market-data fallback.

Reservoir (https://api.reservoir.tools) aggregates NFT collection and token
metadata across EVM chains. This source uses it to:

  1. Discover candidate collections whose name/description mention VRM / 3D
     avatar terms, then validate each candidate by fetching token metadata and
     scanning for VRM pointers via ``scripts.discover_metadata_fields``.
  2. (Optional) Backfill market data (floor price, volume) for collections
     already in the DB.

Per the project methodology, name/description matches are **leads only** — a
collection is only counted as VRM-bearing if a token-metadata VRM pointer
validates via partial-GLB extraction (``scripts.extract_vrm_meta``).

No API key is required for low-volume calls, but ``RESERVOIR_API_KEY`` is
honored if set for higher rate limits.

Usage:
    python sources/reservoir.py --dry-run
    python sources/reservoir.py --search "3d avatar" --validate --dry-run
    python sources/reservoir.py --contract 0xabc --chain ethereum --validate
    python sources/reservoir.py --market-data --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.discover_metadata_fields import scan_metadata, validate_candidates  # noqa: E402
from scripts.extract_vrm_meta import fetch_vrm_meta_safe  # noqa: E402

RESERVOIR_BASE = "https://api.reservoir.tools"
TIMEOUT = 30.0
# Be polite to the public API.
RATE_LIMIT_SLEEP = 0.5

# Search terms that surface VRM/3D-avatar collections.
DEFAULT_SEARCH_TERMS = ["VRM", "3d avatar", "vrm avatar", "metaverse avatar"]

# Name/description substrings that mark a lead as VRM-plausible (not conclusive).
VRM_LEAD_HINTS = ("vrm", "3d avatar", "metaverse avatar", "virtual avatar")


def _api_key() -> str | None:
    return os.environ.get("RESERVOIR_API_KEY")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "superyeti/1.0"}
    key = _api_key()
    if key:
        h["x-api-key"] = key
    return h


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET a Reservoir API endpoint and return parsed JSON."""
    url = f"{RESERVOIR_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- discovery


def search_collections(term: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search Reservoir collections by name. Returns raw collection objects."""
    try:
        data = _get("/search/collections/v1", {"term": term, "limit": limit})
    except urllib.error.HTTPError as e:
        print(f"  search '{term}' failed: HTTP {e.code}", file=sys.stderr)
        return []
    # Reservoir returns {collections: [...]}.
    if isinstance(data, dict):
        return data.get("collections") or []
    return []


def get_collection(contract: str, chain: str = "ethereum") -> dict[str, Any] | None:
    """Fetch a single collection by contract address."""
    try:
        data = _get("/collections/v5", {"contract": contract, "chain": chain})
    except urllib.error.HTTPError as e:
        print(f"  collection {contract} failed: HTTP {e.code}", file=sys.stderr)
        return None
    cols = data.get("collections") if isinstance(data, dict) else None
    return cols[0] if cols else None


def get_token_metadata(contract: str, token_id: str = "1",
                       chain: str = "ethereum") -> dict[str, Any] | None:
    """Fetch token metadata (animation_url, attributes, image) for one token."""
    try:
        data = _get("/tokens/v4", {"contract": contract, "tokenId": token_id,
                                    "chain": chain})
    except urllib.error.HTTPError as e:
        print(f"  token {contract}/{token_id} failed: HTTP {e.code}", file=sys.stderr)
        return None
    tokens = data.get("tokens") if isinstance(data, dict) else None
    return tokens[0] if tokens else None


def _is_lead(collection: dict[str, Any]) -> bool:
    """A collection is a VRM-plausible lead if its name/description mentions
    a VRM hint. This is NOT conclusive — leads must be validated."""
    blob = " ".join(filter(None, [
        collection.get("name"),
        collection.get("description"),
        collection.get("slug"),
    ])).lower()
    return any(hint in blob for hint in VRM_LEAD_HINTS)


def discover_candidates(terms: list[str], validate: bool = False,
                        sample_token_id: str = "1") -> list[dict[str, Any]]:
    """Search for VRM-plausible collections and optionally validate them.

    Returns a list of candidate dicts with keys: name, contract, chain, lead,
    validated (bool|None), vrm_url, vrm_spec.
    """
    seen_contracts: set[str] = set()
    candidates: list[dict[str, Any]] = []

    for term in terms:
        for col in search_collections(term):
            contract = col.get("contract") or col.get("id")
            if not contract or contract in seen_contracts:
                continue
            seen_contracts.add(contract)
            chain = col.get("chain") or "ethereum"
            lead = _is_lead(col)
            cand = {
                "name": col.get("name"),
                "contract": contract,
                "chain": chain,
                "slug": col.get("slug"),
                "lead": lead,
                "validated": None,
                "vrm_url": None,
                "vrm_spec": None,
                "reason": "name/description match" if lead else "search hit, no VRM hint",
            }
            if validate:
                cand = _validate_candidate(cand, sample_token_id)
            candidates.append(cand)
            time.sleep(RATE_LIMIT_SLEEP)

    return candidates


def _validate_candidate(cand: dict[str, Any], token_id: str) -> dict[str, Any]:
    """Fetch token metadata for a candidate and scan for validated VRM pointers."""
    meta = get_token_metadata(cand["contract"], token_id, cand["chain"])
    if not meta:
        cand["validated"] = False
        cand["reason"] = "no token metadata"
        return cand
    # Reservoir nests metadata under 'metadata' or flattens it.
    metadata = meta.get("metadata") or meta
    pointers = scan_metadata(metadata)
    if not pointers:
        cand["validated"] = False
        cand["reason"] = "no VRM pointer in token metadata"
        return cand
    validated = validate_candidates(pointers)
    valid = [p for p in validated if p.get("valid")]
    if valid:
        cand["validated"] = True
        cand["vrm_url"] = valid[0]["url"]
        cand["vrm_spec"] = valid[0].get("vrm_spec")
        cand["reason"] = f"validated VRM pointer ({valid[0]['field']})"
    else:
        cand["validated"] = False
        cand["reason"] = f"{len(pointers)} pointer(s) found, none validated as GLB/VRM"
    return cand


# --------------------------------------------------------------------------- market data


def fetch_market_data(contract: str, chain: str = "ethereum") -> dict[str, Any] | None:
    """Fetch floor price / volume / supply stats for a collection."""
    col = get_collection(contract, chain)
    if not col:
        return None
    stats = col.get("stats") or {}
    return {
        "contract": contract,
        "chain": chain,
        "floor_price": stats.get("floorPrice"),
        "floor_price_symbol": stats.get("symbol"),
        "total_supply": col.get("tokenCount") or stats.get("totalSupply"),
        "one_day_volume": stats.get("1DayVolume"),
        "seven_day_volume": stats.get("7DayVolume"),
        "total_volume": stats.get("totalVolume"),
    }


def backfill_market_data(db_path: str, dry_run: bool = True) -> dict[str, int]:
    """Backfill floor price / volume for collections with a contract but no
    floor_price. Returns a summary dict."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, contract, chain FROM collections
           WHERE contract IS NOT NULL AND floor_price IS NULL
             AND tier IN ('A','B','C') LIMIT 50""",
    ).fetchall()
    updated = 0
    for r in rows:
        md = fetch_market_data(r["contract"], r["chain"] or "ethereum")
        if not md or md["floor_price"] is None:
            continue
        if not dry_run:
            conn.execute(
                """UPDATE collections
                   SET floor_price=?, floor_price_symbol=?,
                       total_volume=?, one_day_volume=?, seven_day_volume=?
                   WHERE id=?""",
                (md["floor_price"], md["floor_price_symbol"],
                 md["total_volume"], md["one_day_volume"],
                 md["seven_day_volume"], r["id"]),
            )
        updated += 1
        time.sleep(RATE_LIMIT_SLEEP)
    if not dry_run:
        conn.commit()
    conn.close()
    return {"checked": len(rows), "updated": updated}


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reservoir EVM candidate discovery + market-data fallback."
    )
    parser.add_argument("--db", default=str(REPO_ROOT / "data" / "vrm_index.db"))
    parser.add_argument("--search", help="single search term (default: built-in list)")
    parser.add_argument("--contract", help="validate a single contract address")
    parser.add_argument("--chain", default="ethereum")
    parser.add_argument("--validate", action="store_true",
                        help="Validate candidates via token-metadata VRM extraction")
    parser.add_argument("--market-data", action="store_true",
                        help="Backfill floor price / volume for existing collections")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results; do not write to the DB")
    args = parser.parse_args(argv)

    if args.market_data:
        print("Reservoir market-data backfill")
        summary = backfill_market_data(args.db, dry_run=args.dry_run)
        print(f"  checked: {summary['checked']}  updated: {summary['updated']}")
        if args.dry_run:
            print("(dry run — no DB writes)")
        return 0

    if args.contract:
        print(f"Validating single contract: {args.contract}")
        col = get_collection(args.contract, args.chain)
        if not col:
            print("  collection not found")
            return 1
        cand = _validate_candidate({
            "name": col.get("name"), "contract": args.contract,
            "chain": args.chain, "slug": col.get("slug"),
            "lead": _is_lead(col), "validated": None,
            "vrm_url": None, "vrm_spec": None, "reason": "",
        }, "1")
        _print_candidate(cand)
        return 0 if cand["validated"] else 1

    terms = [args.search] if args.search else DEFAULT_SEARCH_TERMS
    print(f"Reservoir candidate discovery (terms: {terms})")
    if args.validate:
        print("  Validation enabled — each candidate's token metadata will be scanned")
    candidates = discover_candidates(terms, validate=args.validate)

    leads = [c for c in candidates if c["lead"]]
    validated = [c for c in candidates if c.get("validated")]
    print(f"\n{len(candidates)} candidate(s), {len(leads)} lead(s), "
          f"{len(validated)} validated VRM")
    for c in candidates:
        _print_candidate(c)

    if not args.dry_run and validated:
        print(f"\nWould import {len(validated)} validated collection(s) — "
              "use scripts/resolve_opensea_collections.py to ingest.",
              file=sys.stderr)
    elif args.dry_run:
        print("\n(dry run — no DB writes)")
    return 0


def _print_candidate(c: dict[str, Any]) -> None:
    flag = "VRM" if c.get("validated") else ("LEAD" if c.get("lead") else "   ")
    url = c.get("vrm_url") or "-"
    print(f"  [{flag}] {(c.get('name') or '?')[:30]:30s}  "
          f"{(c.get('contract') or '?')[:12]}...  {url[:60]}")


if __name__ == "__main__":
    raise SystemExit(main())
