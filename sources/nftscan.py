#!/usr/bin/env python3
"""NFTScan source: Linea + Polygon zkEVM candidate discovery.

NFTScan indexes EVM NFT collections on chains that OpenSea/Reservoir coverage
may miss. This source sweeps Linea and Polygon zkEVM collection descriptions
for VRM / 3D-avatar language, then optionally validates token metadata by
running any VRM-looking URL through the partial-GLB extractor.

Name and description matches are **leads only**. A candidate is safe to import
only after a token-metadata VRM pointer validates via ``scripts.extract_vrm_meta``.

Usage:
    NFTSCAN_API_KEY=... python sources/nftscan.py --dry-run
    NFTSCAN_API_KEY=... python sources/nftscan.py --chain linea --search "vrm" --validate --dry-run
    NFTSCAN_API_KEY=... python sources/nftscan.py --contract 0xabc --chain polygon_zkevm --validate
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.discover_metadata_fields import scan_metadata, validate_candidates  # noqa: E402

NFTSCAN_BASE = "https://restapi.nftscan.com/api/v2"
TIMEOUT = 30.0
RATE_LIMIT_SLEEP = 0.5
DEFAULT_CHAINS = ["linea", "polygon_zkevm"]
CHAIN_REFERENCES = {"linea": "59144", "polygon_zkevm": "1101"}
DEFAULT_SEARCH_TERMS = ["VRM", "3d avatar", "metaverse avatar", "virtual avatar"]
VRM_LEAD_HINTS = ("vrm", "3d avatar", "metaverse avatar", "virtual avatar")


def _api_key() -> str | None:
    return os.environ.get("NFTSCAN_API_KEY")


def _headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        raise RuntimeError("NFTSCAN_API_KEY is required for NFTScan requests")
    return {
        "Accept": "application/json",
        "User-Agent": "superyeti/1.0",
        "X-API-KEY": key,
    }


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{NFTSCAN_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _items(payload: Any) -> list[dict[str, Any]]:
    """Extract NFTScan result rows from common response envelopes."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("content", "list", "items", "collections", "assets"):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    data = payload.get("data")
    if data is payload:
        return []
    return _items(data)


def _first_str(obj: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _contract_from(row: dict[str, Any]) -> str | None:
    return _first_str(row, "contract_address", "contract", "address", "token_address")


def _lead_text(row: dict[str, Any]) -> str:
    return " ".join(
        v for v in [
            _first_str(row, "name", "collection_name", "symbol"),
            _first_str(row, "description", "desc", "bio"),
            _first_str(row, "slug"),
        ] if v
    ).lower()


def is_lead(row: dict[str, Any]) -> bool:
    """Return True for name/description hits. This is not VRM proof."""
    text = _lead_text(row)
    return any(hint in text for hint in VRM_LEAD_HINTS)


def search_collections(chain: str, term: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search NFTScan collections by keyword on one chain."""
    try:
        payload = _get("/collections", {"chain": chain, "keyword": term, "limit": limit})
    except urllib.error.HTTPError as e:
        print(f"  NFTScan search {chain}:{term!r} failed: HTTP {e.code}", file=sys.stderr)
        return []
    return _items(payload)


def fetch_collection(contract: str, chain: str) -> dict[str, Any] | None:
    """Fetch one collection by contract address."""
    try:
        payload = _get(f"/collections/{contract}", {"chain": chain})
    except urllib.error.HTTPError as e:
        print(f"  NFTScan collection {chain}:{contract} failed: HTTP {e.code}", file=sys.stderr)
        return None
    rows = _items(payload)
    if rows:
        return rows[0]
    return payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else None


def fetch_sample_assets(contract: str, chain: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch sample asset metadata for a collection.

    NFTScan deployments expose collection assets under ``/assets/{contract}``.
    The response shape varies by chain, so the parser accepts several envelopes.
    """
    try:
        payload = _get(f"/assets/{contract}", {"chain": chain, "limit": limit})
    except urllib.error.HTTPError as e:
        print(f"  NFTScan assets {chain}:{contract} failed: HTTP {e.code}", file=sys.stderr)
        return []
    return _items(payload)


def _candidate_from_collection(row: dict[str, Any], chain: str) -> dict[str, Any]:
    contract = _contract_from(row)
    return {
        "name": _first_str(row, "name", "collection_name", "symbol"),
        "contract": contract,
        "chain": chain,
        "slug": _first_str(row, "slug"),
        "lead": is_lead(row),
        "validated": None,
        "vrm_url": None,
        "vrm_spec": None,
        "vrm_field": None,
        "reason": "name/description match" if is_lead(row) else "search hit, no VRM hint",
        "raw": row,
    }


def rewrite_storage_url(url: str) -> str:
    """Rewrite decentralized storage URIs to HTTPS for binary validation.

    IPFS CIDs are case-sensitive, so the CID/path segment is preserved exactly.
    """
    if not isinstance(url, str):
        return url
    lower = url.lower()
    if lower.startswith("ipfs://"):
        cid = url[len("ipfs://"):].lstrip("/")
        if cid.lower().startswith("ipfs/"):
            cid = cid[5:]
        return "https://ipfs.io/ipfs/" + cid
    if lower.startswith("ar://"):
        return "https://arweave.net/" + url[len("ar://"):].lstrip("/")
    if lower.startswith("arweave://"):
        return "https://arweave.net/" + url[len("arweave://"):].lstrip("/")
    return url


def _validated_hits(metadata_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for obj in metadata_objects:
        candidates.extend(scan_metadata(obj))
    if not candidates:
        return []
    normalized = [
        {**c, "original_url": c["url"], "url": rewrite_storage_url(c["url"])}
        for c in candidates
    ]
    return [hit for hit in validate_candidates(normalized) if hit.get("valid")]


def validate_candidate(candidate: dict[str, Any], sample_limit: int = 10) -> dict[str, Any]:
    """Validate a candidate by scanning collection + sample asset metadata."""
    metadata_objects = [candidate["raw"]]
    contract = candidate.get("contract")
    if contract:
        metadata_objects.extend(fetch_sample_assets(contract, candidate["chain"], sample_limit))
    hits = _validated_hits(metadata_objects)
    if hits:
        candidate["validated"] = True
        candidate["vrm_url"] = hits[0]["url"]
        candidate["vrm_spec"] = hits[0].get("vrm_spec")
        candidate["vrm_field"] = hits[0].get("field")
        candidate["reason"] = f"validated VRM pointer ({hits[0].get('path')})"
    else:
        candidate["validated"] = False
        candidate["reason"] = "no validated VRM pointer in collection/sample metadata"
    return candidate


def discover_candidates(
    chains: list[str],
    terms: list[str],
    validate: bool = False,
    limit: int = 50,
    sample_limit: int = 10,
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for chain in chains:
        for term in terms:
            for row in search_collections(chain, term, limit):
                contract = _contract_from(row)
                if not contract:
                    continue
                key = (chain, contract.lower())
                if key in seen:
                    continue
                seen.add(key)
                cand = _candidate_from_collection(row, chain)
                if validate:
                    cand = validate_candidate(cand, sample_limit)
                out.append(cand)
                time.sleep(RATE_LIMIT_SLEEP)
    return out


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def import_validated(candidates: list[dict[str, Any]], db_path: str, dry_run: bool = True) -> dict[str, int]:
    """Insert only validated VRM collections. Lead-only rows are never imported."""
    valid = [c for c in candidates if c.get("validated") and c.get("contract")]
    if dry_run or not valid:
        return {"checked": len(candidates), "imported": 0, "skipped": len(candidates) - len(valid)}

    conn = sqlite3.connect(db_path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    imported = 0
    try:
        for c in valid:
            contract = c["contract"]
            chain = c["chain"]
            collection_id = _slugify(f"{chain}-{c.get('name') or contract}")
            conn.execute(
                """
                INSERT OR REPLACE INTO collections
                    (id, name, tier, chain, contract, vrm_param, vrm_url_pattern,
                     source, notes)
                VALUES (?, ?, 'A', ?, ?, ?, ?, 'nftscan', ?)
                """,
                (
                    collection_id,
                    c.get("name") or contract,
                    chain,
                    contract,
                    c.get("vrm_field"),
                    c.get("vrm_url"),
                    f"Validated via NFTScan {chain} token metadata at {now}",
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO collection_identifiers
                    (collection_id, namespace, value, chain, contract,
                     verified_at, resolution_source, chain_namespace,
                     chain_reference, asset_namespace)
                VALUES (?, 'nftscan_contract', ?, ?, ?, ?, 'nftscan',
                        'eip155', ?, 'erc721')
                """,
                (collection_id, contract, chain, contract, now, CHAIN_REFERENCES.get(chain)),
            )
            imported += 1
        conn.commit()
    finally:
        conn.close()
    return {"checked": len(candidates), "imported": imported, "skipped": len(candidates) - imported}


def _print_candidate(c: dict[str, Any]) -> None:
    flag = "VRM" if c.get("validated") else ("LEAD" if c.get("lead") else "   ")
    print(
        f"  [{flag}] {c.get('chain', '?'):12s} {(c.get('name') or '?')[:32]:32s} "
        f"{(c.get('contract') or '?')[:14]:14s} {c.get('reason') or ''}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NFTScan Linea + Polygon zkEVM VRM lead sweep.")
    parser.add_argument("--db", default=str(_REPO_ROOT / "data" / "vrm_index.db"))
    parser.add_argument("--chain", action="append", choices=DEFAULT_CHAINS,
                        help="chain to scan; repeatable (default: Linea + Polygon zkEVM)")
    parser.add_argument("--search", action="append",
                        help="search term; repeatable (default: built-in VRM terms)")
    parser.add_argument("--contract", help="validate one contract instead of searching")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--validate", action="store_true",
                        help="validate candidate token metadata via partial-GLB VRM extraction")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="import validated candidates into collections (never imports leads)")
    parser.add_argument("--dry-run", action="store_true", help="print results; do not write")
    args = parser.parse_args(argv)

    chains = args.chain or DEFAULT_CHAINS
    try:
        if args.contract:
            chain = chains[0]
            row = fetch_collection(args.contract, chain) or {"contract_address": args.contract}
            candidates = [_candidate_from_collection(row, chain)]
            if args.validate:
                candidates[0] = validate_candidate(candidates[0], args.sample_limit)
        else:
            candidates = discover_candidates(
                chains,
                args.search or DEFAULT_SEARCH_TERMS,
                validate=args.validate,
                limit=args.limit,
                sample_limit=args.sample_limit,
            )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    leads = [c for c in candidates if c.get("lead")]
    valid = [c for c in candidates if c.get("validated")]
    print(f"NFTScan sweep: {len(candidates)} candidate(s), {len(leads)} lead(s), {len(valid)} validated VRM")
    for c in candidates:
        _print_candidate(c)

    if args.do_import:
        summary = import_validated(candidates, args.db, dry_run=args.dry_run)
        print(f"import: checked={summary['checked']} imported={summary['imported']} skipped={summary['skipped']}")
        if args.dry_run:
            print("(dry run — no DB writes)")
    elif args.dry_run:
        print("(dry run — no DB writes)")
    return 0 if (not args.contract or not args.validate or valid) else 1


if __name__ == "__main__":
    raise SystemExit(main())
